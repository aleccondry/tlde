#ifndef MCUBOOT_FLASH_IMG_COPY_H
#define MCUBOOT_FLASH_IMG_COPY_H

#include <stdint.h>

/**
 * @brief Copy a firmware image from @p partition_id_src into slot1_partition,
 *        request a MCUboot test upgrade, then perform a cold reboot.
 *
 * This function never returns on success because it reboots the device.
 * It only returns a negative errno value if an error occurs before the reboot.
 *
 * @param partition_id_src  flash_area ID of the source partition
 *                          (e.g. FIXED_PARTITION_ID(scratch_partition)).
 * @return Negative errno on failure; does not return on success.
 */
int ubx_mcuboot_flash_img_copy(uint8_t partition_id_src);

#endif /* MCUBOOT_FLASH_IMG_COPY_H */
