import os
import argparse
import sh
from pathlib import Path

from ants import image_read, image_write
from ants import fsl2antstransform, write_transform, apply_transforms
import numpy as np
import nibabel as nib


def bbregister_dat_to_fsl(moving, fixed, register_dat_file, fslmat_file):
    os.environ['FSLOUTPUTTYPE'] = "NIFTI_GZ"

    sh.tkregister2('--mov', moving,
                   '--targ', fixed,
                   '--reg', register_dat_file,
                   '--fslregout', fslmat_file,
                   '--noedit')
    print(f'-->>> {fslmat_file}')
    (register_dat_file.parent / register_dat_file.name.replace('.dat', '.dat~')).unlink(missing_ok=True)


def fsl_to_ants_mat(moving_file, fixed_file, fsl_file, ants_file):
    npfsl = np.loadtxt(fsl_file)

    moving_img = image_read(moving_file)
    fixed_img = image_read(fixed_file)

    tx = fsl2antstransform(npfsl, reference=fixed_img, moving=moving_img)
    write_transform(tx, ants_file)
    print(f'-->>> {ants_file}')


def bold_to_native(moving, fixed, input_transform, moved):
    # 读取固定图像和移动图像
    fixed_img = image_read(fixed)
    moving_img = image_read(moving)

    # 将变换应用到移动图像上
    if len(moving_img.shape) == 4:
        imagetype = 3
    else:
        imagetype = 0
    warped_img = apply_transforms(fixed=fixed_img, moving=moving_img,
                                  transformlist=input_transform, imagetype=imagetype)

    affine_info = nib.load(fixed).affine
    header_info = nib.load(fixed).header

    # save one frame for plotting
    nib_fframe_img = nib.Nifti1Image(warped_img[..., 0].astype(int), affine=affine_info, header=header_info)
    fframe_file = moved.parent / moved.name.replace(".nii.gz", "_fframe.nii.gz")
    nib.save(nib_fframe_img, fframe_file)
    print(f"-->>> output       : {fframe_file}")

    # save
    nib_img = nib.Nifti1Image(warped_img.numpy().astype(int), affine=affine_info, header=header_info)
    nib.save(nib_img, moved)

    # 将结果保存为 NIfTI 格式文件
    # image_write(warped_img, moved)
    print(f"-->>> output       : {moved}")


if __name__ == '__main__':
    """
    --ref /mnt/ngshare/temp/synthmorph/sub-MSC01_0925/sub-MSC01_ses-func01_task-rest_bold_skip_reorient_stc_boldref.nii.gz
    --moving /mnt/ngshare/temp/synthmorph/sub-MSC01_0925/sub-MSC01_ses-func01_task-rest_bold_skip_reorient_stc_mc.nii.gz
    --fixed /mnt/ngshare/temp/synthmorph/sub-MSC01_0925/sub-MSC01_norm_2mm.nii.gz 
    --dat /mnt/ngshare/temp/synthmorph/sub-MSC01_0925/sub-MSC01_ses-func01_task-rest_bold_skip_reorient_stc_mc_from_mc_to_fsnative_bbregister_rigid.dat
    --moved /mnt/ngshare/temp/synthmorph/sub-MSC01_0925/sub-MSC01_ses-func01_task-rest_bold_skip_reorient_stc_boldref_bbregister_space-native_2mm.nii.gz
    --freesurfer-home /usr/local/freesurfer
    """
    # 创建一个命令行解析器
    parser = argparse.ArgumentParser(description='ANTS registration script')

    # 添加需要的命令行参数
    parser.add_argument('--subjects_dir', type=str, help='subjects_dir')
    parser.add_argument('--bold_preprocess_dir', type=str, help='bold_preprocess_dir')
    parser.add_argument('--subject_id', type=str, help='subject_id')
    parser.add_argument('--bold_id', type=str, help='bold_id')
    parser.add_argument('--ref', type=str, help='path to moving image: bold')
    parser.add_argument('--moving', type=str, help='path to moving image: bold')
    parser.add_argument('--fixed', type=str, help='path to fixed image: norm_2mm')
    parser.add_argument('--dat', type=str, help='path to bbregister dat: bbregister.dat')
    # parser.add_argument('--moved', type=str, help='path to moved image: bold_space-native_2mm')
    parser.add_argument('--freesurfer-home', type=str, help='path to freesurfer home', default='/usr/local/freesurfer')

    args = parser.parse_args()

    os.environ['FREESURFER_HOME'] = f"{args.freesurfer_home}"
    os.environ['SUBJECTS_DIR'] = f"{args.freesurfer_home}/subjects"
    os.environ['PATH'] = f"{args.freesurfer_home}/bin:{os.environ['PATH']}"

    print(f'<<<-- {args.moving}')
    print(f'<<<-- {args.fixed}')
    print(f'<<<-- {args.dat}')
    print(f'<<<-- {args.freesurfer_home}')

    cur_path = os.getcwd()

    preprocess_dir = Path(cur_path) / str(args.bold_preprocess_dir) / args.subject_id
    subj_func_dir = Path(preprocess_dir) / 'func'
    subj_func_dir.mkdir(parents=True, exist_ok=True)

    ref = subj_func_dir / f'{args.bold_id}_skip_reorient_stc_boldref.nii.gz'
    moving = subj_func_dir / f'{args.bold_id}_skip_reorient_stc_mc.nii.gz'
    fixed = subj_func_dir / f'{args.subject_id}_T1_2mm.nii.gz'
    dat = subj_func_dir / f'{args.bold_id}_skip_reorient_stc_mc_from_mc_to_fsnative_bbregister_rigid.dat'
    moved = subj_func_dir / f'{args.bold_id}_skip_reorient_stc_mc_bbregister_space-native_2mm.nii.gz'

    tfm_fsl = str(dat).replace('.dat', '.fsl')
    tfm_mat = str(dat).replace('.dat', '.mat')
    transforms = [tfm_mat]

    bbregister_dat_to_fsl(ref, fixed, dat, tfm_fsl)
    fsl_to_ants_mat(str(ref), str(fixed), tfm_fsl, tfm_mat)
    bold_to_native(str(moving), str(fixed), transforms, moved)