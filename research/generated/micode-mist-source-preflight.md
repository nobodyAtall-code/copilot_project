# MiCode Mist kernel source preflight

PASS: 11 pinned upstream/owned revisions and required files verified.

Correct upstream branch: mist-w-oss, NOT mist-oss.

Owned kernel_build matches upstream tracked source tree; no reset/clone replacement required.

## Verified source pins

- nobodyAtall-code/android_kernel_xiaomi_mist (main): fe8024a4c5eea6cf1135e615d44e7a3fb15fedac
- nobodyAtall-code/kernel_build (main): ee8c9d048bfda42314e5cdb2d4ab8bd56b73fa19
- MiCode/kernel_build (mist-w-oss): 9ab26a75077949242e32748dcb8ea46fa3a5bba8
- MiCode/Xiaomi_Kernel_OpenSource (mist-w-oss): 828fe3bef1d1f16dd280da29f17b56059c06134e
- MiCode/kernel_devicetree (mist-w-oss): 55966b16689be0d8619c9e7b8146c6e268851844
- MiCode/vendor_qcom_opensource_wlan (mist-w-oss): 500816b7e9c458c65c465c3999e167214b084207
- MiCode/vendor_qcom_opensource_audio-kernel (mist-w-oss): 5dd1fa6e664ad76685f1a1c02b079a4db3385555
- MiCode/vendor_qcom_opensource_data-kernel (mist-w-oss): 4282d9652a4b7cfde38461c2938852423687ef8f
- MiCode/vendor_qcom_opensource_camera-kernel (mist-w-oss): 74d0b79ca87dcfe269ea556537ce840e2dc0ff43
- MiCode/vendor_qcom_proprietary_display-devicetree (mist-w-oss): 40f37b6254f54a7b5b2a718915851902e03598ae
- MiCode/vendor_qcom_proprietary_camera-devicetree (mist-w-oss): efd42dcc2817e98971cf832acb0bc10083fea4d7

## Still required

- Isolated Kleaf workspace with compiler, Bazel and all external kernel module directories
- Full source build, generated DTB/DTBO comparison with verified stock firmware
- Module ABI and boot validation before switching away from stock kernel prebuilt

This PASS is source provenance only, not a successful kernel build.
