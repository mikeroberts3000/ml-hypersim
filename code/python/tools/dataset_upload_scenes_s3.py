from pylab import *

import argparse
import fnmatch
import glob
import inspect
import os
import pandas as pd
import posixpath

import path_utils
path_utils.add_path_to_sys_path("..", mode="relative_to_current_source_dir", frame=inspect.currentframe())
import _system_config

parser = argparse.ArgumentParser()
parser.add_argument("--dataset_dir", required=True)
parser.add_argument("--dataset_dir_s3")
parser.add_argument("--scene_names")
parser.add_argument("--analysis_dir")
parser.add_argument("--check_http_zip_files", action="store_true")
parser.add_argument("--dataset_dir_http")
args = parser.parse_args()

assert os.path.exists(args.dataset_dir)

if args.check_http_zip_files:
    assert args.dataset_dir_http is not None
else:
    assert args.dataset_dir_s3 is not None

path_utils.add_path_to_sys_path(args.dataset_dir, mode="relative_to_cwd", frame=inspect.currentframe())
import _dataset_config



print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3] Begin...")



tmp_dir            = os.path.join(args.dataset_dir, "_tmp")
dataset_scenes_dir = os.path.join(args.dataset_dir, "scenes")

if args.scene_names is not None:
    scenes = [ s for s in _dataset_config.scenes if fnmatch.fnmatch(s["name"], args.scene_names) ]
else:
    scenes = _dataset_config.scenes

metadata_images_csv_file = os.path.join(args.analysis_dir, "metadata_images.csv")
df_images = pd.read_csv(metadata_images_csv_file).rename_axis("image_guid").reset_index().set_index(["scene_name", "camera_name"])



# if we're checking public zip files, create session
if args.check_http_zip_files:
        import requests
        session = requests.session()



def check_http(files, base_dir, session, zip_file_url):

    files_expanded = []
    for f in files:
        if "*" in f:
            f_expanded = glob.glob(os.path.join(base_dir, f), recursive=True)
            for fe in f_expanded:
                if os.path.isfile(fe):
                    files_expanded.append(os.path.relpath(fe, start=base_dir))
        else:
            files_expanded.append(f)

    # check that each file in the files-to-upload list exists on disk
    for fe in files_expanded:
        if not os.path.exists(os.path.join(base_dir, fe)):
            print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3] WARNING (MISSING FROM DISK): " + f)

    # check that each file in the files-to-upload list already exists in public zip file, and
    # that each file in the public zip file exists in the files-to-upload list

    import posixpath
    import zipfile
    path_utils.add_path_to_sys_path("../../../contrib/99991", mode="relative_to_current_source_dir", frame=inspect.currentframe())
    import download

    # e.g., https://docs-assets.developer.apple.com/ml-research/datasets/hypersim/v1/scenes/ai_001_001.zip
    f = download.WebFile(zip_file_url, session)
    z = zipfile.ZipFile(f)

    zip_files = []
    for entry in z.infolist():
        if entry.is_dir():
            continue
        zip_files.append(entry.filename)

    # for each file in the files-to-upload list
    for f in files_expanded:
        if f not in zip_files:
            print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3] WARNING (MISSING FROM PUBLIC ZIP): " + f)

    # for each file in the public zip file
    for z in zip_files:
        if z not in files_expanded:
            print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3] WARNING (MISSING FROM FILES-TO-UPLOAD LIST): " + z)



def upload_s3(files, base_dir, tmp_files_txt_file, tmp_zip_file, zip_file_full_path_s3):

    files_expanded = []
    for f in files:
        if "*" in f:
            f_expanded = glob.glob(os.path.join(base_dir, f), recursive=True)
            for fe in f_expanded:
                if os.path.isfile(fe):
                    files_expanded.append(os.path.relpath(fe, start=base_dir))
        else:
            files_expanded.append(f)

    # check that each file in the files-to-upload list exists on disk
    for fe in files_expanded:
        if not os.path.exists(os.path.join(base_dir, fe)):
            print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3] WARNING (MISSING FROM DISK): " + f)

    # We don't want to create these files in a temp folder because the structure of the zip file is sensitive
    # to the current working directory.
    zip_file_full_path = os.path.join(base_dir, tmp_zip_file)

    cwd = os.getcwd()
    os.chdir(base_dir)

    if os.path.exists(tmp_zip_file):
        os.remove(tmp_zip_file)

    files_str = "\n".join(files_expanded)
    with open(tmp_files_txt_file, "w") as f:
        f.write(files_str)

    cmd = _system_config.compress_bin + " a -mx=0 -tzip -spf " + tmp_zip_file + " @" + tmp_files_txt_file
    print("")
    print(cmd)
    print("")
    retval = os.system(cmd)
    assert retval == 0

    cmd = _system_config.aws_bin + " s3 cp " + zip_file_full_path + " " + zip_file_full_path_s3
    print("")
    print(cmd)
    print("")
    retval = os.system(cmd)
    assert retval == 0

    os.remove(tmp_files_txt_file)
    os.remove(tmp_zip_file)

    os.chdir(cwd)



# global asset files
files = [os.path.join("_asset", "**")]

if args.check_http_zip_files:
    check_http(files, base_dir=args.dataset_dir, session=session, zip_file_url=posixpath.join(args.dataset_dir_http, "_asset.zip"))
else:
    upload_s3(files, base_dir=args.dataset_dir, tmp_files_txt_file="_tmp_asset_files.txt", tmp_zip_file="_tmp_asset.zip", zip_file_full_path_s3=posixpath.join(args.dataset_dir_s3, "_asset.zip"))



for s in scenes:

    scene_name = s["name"]

    # This case is possible when the camera trajectory generation step fails for the entire scene.
    if scene_name not in df_images.index:
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3] WARNING: scene_name " + scene_name + " IS DEFINED IN _dataset_config.py BUT IS NOT DEFINED IN metadata_images.csv, skipping...")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        continue

    df_images_scene = df_images.loc[scene_name]
    images_scene = df_images_scene.to_records()

    if not any(df_images_scene["included_in_public_release"].to_numpy()):
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3] No images to be included in public release for scene_name " + scene_name + ", skipping...")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3]")
        continue

    files = []

    # original asset files
    files.append(os.path.join(scene_name, "_asset", "**"))

    # exported asset files
    files.append(os.path.join(scene_name, "_asset_export", "cam_*.csv"))
    files.append(os.path.join(scene_name, "_asset_export", "metadata_cameras_asset_export.csv"))
    files.append(os.path.join(scene_name, "_asset_export", "scene.mtl"))
    files.append(os.path.join(scene_name, "_asset_export", "scene.obj"))
    files.append(os.path.join(scene_name, "_asset_export", "scene.vrscene"))

    # mesh files
    files.append(os.path.join(scene_name, "_detail", "mesh", "mesh_faces_gi.hdf5"))
    files.append(os.path.join(scene_name, "_detail", "mesh", "mesh_faces_mi.hdf5"))
    files.append(os.path.join(scene_name, "_detail", "mesh", "mesh_faces_oi.hdf5"))
    files.append(os.path.join(scene_name, "_detail", "mesh", "mesh_faces_vi.hdf5"))
    files.append(os.path.join(scene_name, "_detail", "mesh", "mesh_faces_vni.hdf5"))
    files.append(os.path.join(scene_name, "_detail", "mesh", "mesh_faces_vti.hdf5"))
    files.append(os.path.join(scene_name, "_detail", "mesh", "mesh_normals.hdf5"))
    files.append(os.path.join(scene_name, "_detail", "mesh", "mesh_texcoords.hdf5"))
    files.append(os.path.join(scene_name, "_detail", "mesh", "mesh_vertices.hdf5"))
    files.append(os.path.join(scene_name, "_detail", "mesh", "metadata_groups.csv"))
    files.append(os.path.join(scene_name, "_detail", "mesh", "metadata_materials.csv"))

    if args.check_http_zip_files:
        check_http(files, base_dir=dataset_scenes_dir, session=session, zip_file_url=posixpath.join(args.dataset_dir_http, "scenes", scene_name + ".zip"))
        continue
    else:
        upload_s3(files, base_dir=dataset_scenes_dir, tmp_files_txt_file="_tmp_" + scene_name + "_files.txt", tmp_zip_file="_tmp_" + scene_name + ".zip", zip_file_full_path_s3=posixpath.join(args.dataset_dir_s3, "scenes", scene_name + ".zip"))



print("[HYPERSIM: DATASET_UPLOAD_SCENES_S3] Finished.")
