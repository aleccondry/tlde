/*
 * Pure Zephyr C translation of the Rust flash_test / ubx_flash_test module.
 *
 * Flash area used: slot1_partition (defined in the board DTS).
 * All operations go through the Zephyr flash-area / flash-driver APIs:
 *   - flash_area_open / flash_area_close
 *   - flash_area_erase / flash_area_write / flash_area_read
 *   - flash_get_page_info_by_offs  (page size)
 *   - flash_get_parameters         (erase value, write-block size)
 */

#include "flash_test.h"

#include <errno.h>
#include <string.h>

#include <zephyr/drivers/flash.h>
#include <zephyr/logging/log.h>
#include <zephyr/storage/flash_map.h>

LOG_MODULE_DECLARE(flash_rw, LOG_LEVEL_DBG);

/* Number of bytes written / read in the self-test chunk. */
#define CHUNK_SIZE_BYTES 128

/* -------------------------------------------------------------------------
 * Internal helpers
 * ---------------------------------------------------------------------- */

/**
 * Retrieve the flash page size that covers byte offset 0 of the given area.
 * The offset passed to flash_get_page_info_by_offs must be absolute (within
 * the flash device), so we add the area's starting offset.
 */
static int get_page_size(const struct flash_area *fa, size_t *page_size)
{
    const struct device *dev = flash_area_get_device(fa);

    if (!device_is_ready(dev)) {
        return -ENODEV;
    }

    struct flash_pages_info info;
    int err = flash_get_page_info_by_offs(dev, fa->fa_off, &info);

    if (err) {
        return err;
    }

    *page_size = info.size;
    return 0;
}

/* -------------------------------------------------------------------------
 * flash_test  (private, mirrors the Rust flash_test() -> Result<()>)
 * ---------------------------------------------------------------------- */

static int flash_test(void)
{
    const struct flash_area *fa;
    int err;

    err = flash_area_open(FIXED_PARTITION_ID(slot1_partition), &fa);
    if (err) {
        LOG_ERR("failed to open flash partition: %d", err);
        return err;
    }

    LOG_INF("UpdateBox: flash test");

    /* Log partition geometry (mirrors FlashPartition::log_config). */
    size_t page_size;
    err = get_page_size(fa, &page_size);
    if (err) {
        LOG_ERR("failed to get page size: %d", err);
        goto out;
    }

    LOG_INF("  partition size   : %zu bytes", (size_t)fa->fa_size);
    LOG_INF("  page size        : %zu bytes", page_size);

    /* Erase one full page starting at offset 0. */
    const off_t  offset    = 0;
    const size_t num_bytes = page_size;

    LOG_INF("erase complete page, it may take a few seconds");
    err = flash_area_erase(fa, offset, num_bytes);
    if (err) {
        LOG_ERR("erase failed: %d", err);
        goto out;
    }
    LOG_INF("erased %zu bytes at 0x%lx", num_bytes, (unsigned long)offset);

    /* Write one chunk: bytes 0x00 … 0x7F. */
    uint8_t write_buffer[CHUNK_SIZE_BYTES];

    for (int i = 0; i < CHUNK_SIZE_BYTES; i++) {
        write_buffer[i] = (uint8_t)i;
    }

    err = flash_area_write(fa, offset, write_buffer, CHUNK_SIZE_BYTES);
    if (err) {
        LOG_ERR("write failed: %d", err);
        goto out;
    }
    LOG_INF("wrote 1 chunk of %d bytes to 0x%lx",
            CHUNK_SIZE_BYTES, (unsigned long)offset);

    /* Read it back. */
    uint8_t read_buffer[CHUNK_SIZE_BYTES];

    err = flash_area_read(fa, offset, read_buffer, CHUNK_SIZE_BYTES);
    if (err) {
        LOG_ERR("read failed: %d", err);
        goto out;
    }

    /* Compare. */
    int diff = 0;

    for (int i = 0; i < CHUNK_SIZE_BYTES; i++) {
        if (read_buffer[i] != write_buffer[i]) {
            diff++;
        }
    }

    if (diff > 0) {
        LOG_ERR("%d mismatches found", diff);
        err = -EIO;
        goto out;
    }

    LOG_INF("wrote and read 1 chunk of %d bytes", CHUNK_SIZE_BYTES);

out:
    flash_area_close(fa);
    return err;
}

/* -------------------------------------------------------------------------
 * Public C API  (mirrors the #[no_mangle] Rust exports)
 * ---------------------------------------------------------------------- */

int ubx_flash_test(void)
{
    int err = flash_test();

    if (err) {
        LOG_ERR("flash test failed: %d", err);
    }

    return err;
}
