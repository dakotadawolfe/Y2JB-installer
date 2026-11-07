/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "assets.h"
#include "image.h"
#include "crypto/sha256.h"
#include "install/install.h"
#include "install/installed.h"
#include <ps5/kernel.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#ifndef WORK
#define WORK "/data/y2jb-installer"
#endif
#define TITLE "PPSA01650"
#ifndef DIR
#define DIR "/user/download/" TITLE
#endif
#define TARGET DIR "/download0.dat"
int sceKernelSendNotificationRequest(int,void *,size_t,int);
static void notice(const char *text) {
    struct { char reserved[45]; char message[3075]; } n={0};
    snprintf(n.message,sizeof n.message,"%s",text);
    sceKernelSendNotificationRequest(0,&n,sizeof n,0);
}
static int directory(const char *path) {
    struct stat st;
    if(mkdir(path,0755) && errno!=EEXIST) return -1;
    return lstat(path,&st) || !S_ISDIR(st.st_mode) ? -1 : 0;
}
static int regular_or_absent(const char *path) {
    struct stat st;
    if(lstat(path,&st)) return errno==ENOENT?0:-1;
    return S_ISREG(st.st_mode)?1:-1;
}
static int matches(const char *path,const char *expected) {
    char hash[65];return regular_or_absent(path)==1 && !compute_sha256_file(path,hash) && !strcmp(hash,expected);
}
static int embedded(const unsigned char *start,const unsigned char *end,const char *expected) {
    unsigned char hash[32];char hex[65];SHA256_CTX ctx;
    sha256_init(&ctx);sha256_update(&ctx,start,(size_t)(end-start));sha256_final(&ctx,hash);
    for(size_t i=0;i<32;i++)snprintf(hex+2*i,3,"%02x",hash[i]);
    return !strcmp(hex,expected);
}
static int write_all(int fd,const unsigned char *data,size_t n) {
    while(n) { ssize_t r=write(fd,data,n);if(r<0 && errno==EINTR)continue;if(r<=0)return -1;data+=r;n-=(size_t)r; }
    return 0;
}
static int stage_package(void) {
    const char *path=WORK "/youtube.pkg";
    if(matches(path,PACKAGE_SHA))return 0;
    if(regular_or_absent(path)<0)return -1;
    if(unlink(path) && errno!=ENOENT)return -1;
    int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(fd<0)return -1;
    int rc=write_all(fd,package_start,(size_t)(package_end-package_start)) || fsync(fd);
    if(close(fd))rc=1;
    return rc || !matches(path,PACKAGE_SHA)?-1:0;
}
static int closed(void) {
    for(int i=0;i<3;i++) {char p[128];struct stat st;snprintf(p,sizeof p,"/mnt/sandbox/" TITLE "_%03d",i);
        if(!lstat(p,&st) || errno!=ENOENT)return 0;
    }return 1;
}
static int backup_existing(char *backup,size_t cap) {
    int state=regular_or_absent(TARGET);if(state<=0)return state;
    snprintf(backup,cap,WORK "/download0-%lld-%ld.bak",(long long)time(NULL),(long)getpid());
    int in=open(TARGET,O_RDONLY|O_NOFOLLOW);if(in<0)return -1;
    int out=open(backup,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(out<0){close(in);return -1;}
    unsigned char buffer[65536];ssize_t n;int rc=0;
    while((n=read(in,buffer,sizeof buffer))!=0) {
        if(n<0 && errno==EINTR)continue;
        if(n<0 || write_all(out,buffer,(size_t)n)){rc=-1;break;}
    }
    if(fsync(out))rc=-1;
    if(close(out))rc=-1;
    close(in);
    char before[65],after[65];
    if(!rc && (compute_sha256_file(TARGET,before) || compute_sha256_file(backup,after) || strcmp(before,after)))rc=-1;
    return rc;
}
static int install_image(void) {
    if(matches(TARGET,IMAGE_FULL_SHA))return 0;
    if(!closed() || directory(DIR))return -1;
    char tmp[256],backup[256]={0};
    snprintf(tmp,sizeof tmp,DIR "/download0.dat.install-%ld",(long)getpid());
    int fd=open(tmp,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0644);if(fd<0)return -1;
    int rc=image_write(fd,image_start,(size_t)(image_end-image_start),IMAGE_SIZE);
    if(close(fd))rc=-1;
    if(!rc && !matches(tmp,IMAGE_FULL_SHA))rc=-1;
    if(!rc && backup_existing(backup,sizeof backup))rc=-1;
    if(!rc && (!closed() || regular_or_absent(TARGET)<0 || rename(tmp,TARGET)))rc=-1;
    if(rc) {unlink(tmp);return -1;}
    int dir=open(DIR,O_RDONLY|O_DIRECTORY);if(dir<0)return -1;
    rc=fsync(dir);close(dir);
    if(backup[0])printf("Previous download0.dat saved at %s\n",backup);
    return rc || !matches(TARGET,IMAGE_FULL_SHA)?-1:0;
}
int main(void) {
    signal(SIGPIPE,SIG_IGN);
    if((kernel_get_fw_version()&0xffff0000u)!=0x13600000u || geteuid()!=0) {
        notice("Y2JB installer requires a privileged PS5 13.60 session.");return 1;
    }
    if(directory(WORK))return 1;
    int lock=open(WORK "/install.lock",O_CREAT|O_RDWR|O_NOFOLLOW,0600);struct stat st;
    if(lock<0 || fstat(lock,&st) || !S_ISREG(st.st_mode) || flock(lock,LOCK_EX|LOCK_NB)) {
        if(lock>=0)close(lock);notice("Y2JB installer is already running or unavailable.");return 1;
    }
    int rc=1;struct statvfs space;
    if(!closed()){notice("Close YouTube completely before installing Y2JB.");goto end;}
    if(statvfs("/user",&space) || (uint64_t)space.f_bavail*space.f_frsize<2ULL*1024*1024*1024 ||
       statvfs(WORK,&space) || (uint64_t)space.f_bavail*space.f_frsize<2ULL*1024*1024*1024) {
        notice("Y2JB installation needs at least 2 GiB of free storage.");goto end;
    }
    if(!embedded(package_start,package_end,PACKAGE_SHA) || !embedded(image_start,image_end,IMAGE_PACKED_SHA) ||
       image_validate(image_start,(size_t)(image_end-image_start),IMAGE_SIZE)) {
        notice("Y2JB installer data verification failed.");goto end;
    }
    installed_info_t info;installed_read(TITLE,&info);
    if(info.installed && strcmp(info.package_digest,PACKAGE_DIGEST)) {
        notice("A different YouTube package is installed. Nothing was replaced.");goto end;
    }
    notice("Installing YouTube and Y2JB...");
    if(!info.installed) {
        if(stage_package() || install_start(TITLE,WORK "/youtube.pkg",PACKAGE_DIGEST,0))goto failed;
        install_status_t status;
        do {sleep(1);install_status(&status);}while(status.state==INSTALL_RUNNING);
        if(status.state!=INSTALL_DONE){printf("Package installation: %s\n",status.message);goto failed;}
        installed_read(TITLE,&info);
        if(!info.installed || strcmp(info.package_digest,PACKAGE_DIGEST))goto failed;
    }
    if(install_image())goto failed;
    if(matches(WORK "/youtube.pkg",PACKAGE_SHA))unlink(WORK "/youtube.pkg");
    notice("Y2JB installed. You can now launch YouTube.");rc=0;goto end;
failed:
    notice("Y2JB installation did not finish. Check the payload log.");
end:
    close(lock);return rc;
}
