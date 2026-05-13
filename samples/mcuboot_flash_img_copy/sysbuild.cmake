# Copyright (c) 2024 Nordic Semiconductor ASA
# SPDX-License-Identifier: Apache-2.0

# Image incorrectly signed
ExternalZephyrProject_Add(
  APPLICATION img_v1_0_0
  SOURCE_DIR ${APP_DIR}/img_v1_0_0
)

# Image correctly signed
ExternalZephyrProject_Add(
  APPLICATION img_v2_0_0
  SOURCE_DIR ${APP_DIR}/img_v2_0_0
)
