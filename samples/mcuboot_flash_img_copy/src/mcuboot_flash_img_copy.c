/*
 * Pure Zephyr C translation of the Rust mcuboot_flash_img_copy module.
 *
 * Copies a firmware image from a source flash partition into slot1_partition,
 * requests a test upgrade via MCUboot, then performs a cold reboot.
 *
 * APIs used:
 *   - flash_area_open / flash_area_close / flash_area_erase / flash_area_write / flash_area_read
 *   - boot_fetch_active_slot / boot_read_bank_header
 *   - mcuboot_swap_type / boot_request_upgrade
 *   - sys_reboot
 */

#include "mcuboot_flash_img_copy.h"

#include <errno.h>

#include <zephyr/dfu/mcuboot.h>
#include <zephyr/drivers/flash.h>
#include <zephyr/logging/log.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/sys/reboot.h>

LOG_MODULE_DECLARE(mcuboot_flash_img_copy, LOG_LEVEL_DBG);

/* Chunk size used when copying image data between partitions. */
#define FLASH_CHUNK_SIZE 256U

/* -------------------------------------------------------------------------
 * Internal helper: swap-type value → human-readable string
 * ---------------------------------------------------------------------- */

static const char *swap_type_str(int swap_type)
{
    switch (swap_type) {
    case BOOT_SWAP_TYPE_NONE:    return "NONE";
    case BOOT_SWAP_TYPE_TEST:    return "TEST";
    case BOOT_SWAP_TYPE_PERM:    return "PERM";
    case BOOT_SWAP_TYPE_REVERT:  return "REVERT";
    case BOOT_SWAP_TYPE_FAIL:    return "FAIL";
    default:                     return "UNKNOWN";
    }
}

/* -------------------------------------------------------------------------
 * Private implementation (mirrors Rust mcuboot_flash_img_copy())
 * ---------------------------------------------------------------------- */

static int mcuboot_flash_img_copy(uint8_t partition_id_src)
{
    int err;

    LOG_INF("Updatebox: copy image from storage to slot1");

    /* -----------------------------------------------------------------
     * Log active-slot / swap-type information.
     * --------------------------------------------------------------- */
    uint8_t flash_area_id = boot_fetch_active_slot();
    int swap = mcuboot_swap_type();

    LOG_INF("Swap type: %s (%d)", swap_type_str(swap), swap);
    LOG_INF("Active partition id: %u", (unsigned)flash_area_id);

    /* -----------------------------------------------------------------
     * Read and log the image header from the active slot.
     * --------------------------------------------------------------- */
    struct mcuboot_img_header boot_header;

    err = boot_read_bank_header(flash_area_id, &boot_header, sizeof(boot_header));
    if (err) {
        LOG_ERR("boot_read_bank_header() failed: %d", err);
        return err;
    }

    const struct mcuboot_img_sem_ver *ver = &boot_header.h.v1.sem_ver;

    LOG_INF("Image Version: %u.%u.%u (build %u)",
            (unsigned)ver->major,
            (unsigned)ver->minor,
            (unsigned)ver->revision,
            (unsigned)ver->build_num);

    /* -----------------------------------------------------------------
     * Open source and destination flash partitions.
     * --------------------------------------------------------------- */
    const struct flash_area *fa_dest;
    const struct flash_area *fa_src;

    err = flash_area_open(FIXED_PARTITION_ID(slot1_partition), &fa_dest);
    if (err) {
        LOG_ERR("failed to open slot1_partition: %d", err);
        return err;
    }

    LOG_INF("dest partition size: %zu bytes, offset: 0x%lx",
            (size_t)fa_dest->fa_size, (unsigned long)fa_dest->fa_off);

    err = flash_area_open(partition_id_src, &fa_src);
    if (err) {
        LOG_ERR("failed to open source partition %u: %d",
                (unsigned)partition_id_src, err);
        flash_area_close(fa_dest);
        return err;
    }

    /* -----------------------------------------------------------------
     * Determine copy size: minimum of the two partition sizes.
     * --------------------------------------------------------------- */
    size_t copy_size = fa_src->fa_size < fa_dest->fa_size
                       ? fa_src->fa_size
                       : fa_dest->fa_size;

    /* copy_size must be an exact multiple of FLASH_CHUNK_SIZE. */
    if (copy_size % FLASH_CHUNK_SIZE != 0) {
        LOG_ERR("copy_size %zu is not a multiple of chunk size %u",
                copy_size, FLASH_CHUNK_SIZE);
        err = -EINVAL;
        goto close_both;
    }

    uint32_t nb_chunks = (uint32_t)(copy_size / FLASH_CHUNK_SIZE);

    /* -----------------------------------------------------------------
     * Erase the destination partition.
     * --------------------------------------------------------------- */
    err = flash_area_erase(fa_dest, 0, copy_size);
    if (err) {
        LOG_ERR("erase of slot1_partition failed: %d", err);
        goto close_both;
    }

    LOG_INF("erased %zu bytes", copy_size);

    /* -----------------------------------------------------------------
     * Copy image in FLASH_CHUNK_SIZE chunks.
     * --------------------------------------------------------------- */
    uint8_t copy_buffer[FLASH_CHUNK_SIZE];

    LOG_INF("Copy %u chunks of %u B", (unsigned)nb_chunks, FLASH_CHUNK_SIZE);

    for (uint32_t chunk = 0; chunk < nb_chunks; chunk++) {
        off_t offset = (off_t)(chunk * FLASH_CHUNK_SIZE);

        err = flash_area_read(fa_src, offset, copy_buffer, FLASH_CHUNK_SIZE);
        if (err) {
            LOG_ERR("read failed at offset 0x%lx: %d",
                    (unsigned long)offset, err);
            goto close_both;
        }

        err = flash_area_write(fa_dest, offset, copy_buffer, FLASH_CHUNK_SIZE);
        if (err) {
            LOG_ERR("write failed at offset 0x%lx: %d",
                    (unsigned long)offset, err);
            goto close_both;
        }
    }

    /* -----------------------------------------------------------------
     * Request a test upgrade and log the new swap type.
     * --------------------------------------------------------------- */
    LOG_INF("Requesting test upgrade");

    err = boot_request_upgrade(BOOT_UPGRADE_TEST);
    if (err) {
        LOG_ERR("boot_request_upgrade() failed: %d", err);
        goto close_both;
    }

    swap = mcuboot_swap_type();
    LOG_INF("Swap type: %s (%d)", swap_type_str(swap), swap);

close_both:
    flash_area_close(fa_src);
    flash_area_close(fa_dest);
    return err;
}

/* -------------------------------------------------------------------------
 * Public C API
 * ---------------------------------------------------------------------- */

int ubx_mcuboot_flash_img_copy(uint8_t partition_id_src)
{
    int err = mcuboot_flash_img_copy(partition_id_src);

    if (err) {
        LOG_ERR("mcuboot_flash_img_copy() failed: %d", err);
        return err;
    }

    LOG_INF("Will attempt to reboot device");

    /* sys_reboot() does not return on success. */
    sys_reboot(SYS_REBOOT_COLD);

    /* Unreachable, but satisfies the compiler. */
    return -EIO;
}
