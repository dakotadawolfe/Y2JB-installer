/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "image.h"
#include <errno.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
static uint64_t le(const unsigned char *p, size_t n) {
    uint64_t v=0; for(size_t i=0;i<n;i++) v|=(uint64_t)p[i]<<(8*i); return v;
}
int image_validate(const unsigned char *data, size_t n, uint64_t size) {
    if(n<16 || memcmp(data,"Y2JBIMG1",8) || le(data+8,8)!=size || size>INT64_MAX) return -1;
    size_t p=16; uint64_t end=0;
    while(p<n) {
        if(n-p<12) return -1;
        uint64_t off=le(data+p,8), len=le(data+p+8,4); p+=12;
        if(!len || len>65536 || off<end || off>size || len>size-off || len>n-p) return -1;
        end=off+len; p+=(size_t)len;
    }
    return 0;
}
int image_write(int fd, const unsigned char *data, size_t n, uint64_t size) {
    if(image_validate(data,n,size) || ftruncate(fd,0) || ftruncate(fd,(off_t)size)) return -1;
    for(size_t p=16;p<n;) {
        uint64_t off=le(data+p,8); size_t len=(size_t)le(data+p+8,4); p+=12;
        size_t done=0;
        while(done<len) {
            ssize_t r=pwrite(fd,data+p+done,len-done,(off_t)(off+done));
            if(r<0 && errno==EINTR) continue;
            if(r<=0) return -1;
            done+=(size_t)r;
        }
        p+=len;
    }
    return fsync(fd);
}
