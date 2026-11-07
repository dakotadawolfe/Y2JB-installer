/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include <stddef.h>
#include <stdint.h>
int image_validate(const unsigned char *data, size_t length, uint64_t expected_size);
int image_write(int fd, const unsigned char *data, size_t length, uint64_t expected_size);
