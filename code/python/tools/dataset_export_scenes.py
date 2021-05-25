from pylab import *

import argparse
import distutils.dir_util
import inspect
import os
import shlex
import shutil
import subprocess
import sys

import path_utils
path_utils.add_path_to_sys_path("..", mode="relative_to_current_source_dir", frame=inspect.currentframe())
import _system_config

assert sys.platform == "win32"
assert os.path.exists(_system_config.max_sceneassets_photometric_dir)
assert os.path.exists(_system_config.max_plugcfg_dir)

parser = argparse.ArgumentParser()
parser.add_argument("--dataset_dir", required=True)
parser.add_argument("--scene_names")
args = parser.parse_args()

assert os.path.exists(args.dataset_dir)



print("[HYPERSIM: DATASET_EXPORT_SCENES] Begin...")



# set up OBJ export
obj_settings_file        = os.path.join(_system_config.max_plugcfg_dir, _system_config.max_objexp_ini_file)
obj_settings_backup_file = os.path.join(args.dataset_dir, "_tmp", "_" + _system_config.max_objexp_ini_file)

if os.path.exists(obj_settings_file):
    print("[HYPERSIM: DATASET_EXPORT_SCENES] Configuring " + obj_settings_file + ", saving a backup at " + obj_settings_backup_file + "...")
    shutil.copy(obj_settings_file, obj_settings_backup_file)
else:
    print("[HYPERSIM: DATASET_EXPORT_SCENES] Creating " + obj_settings_file + "...")

# it would be cleaner to do this with the ConfigParser library
obj_settings_str = \
"""[General]
UseLogging=1
Preset=<NONE>
MapSearchPath=

[Geometry]
FlipZyAxis=0
Shapes=0
ExportHiddenObjects=0
FaceType=0
TextureCoords=1
Normals=1
SmoothingGroups=0
ObjScale=1.000000

[Material]
UseMaterial=1
CreateMatLibrary=1
ForceBlackAmbient=0
UseMapPath=0
MapPath=./maps/
AutoMapChannel=0
MapChannel=1
ExtendedParams=0
ConvertBitmaps=0
RenderProcedural=1
ResizeMaps=0
ResizeMaps2n=0
MapFormat=3
MapSizeX=512
MapSizeY=512

[Output]
RelativeIndex=0
Target=0
Precision=20

[Optimize]
optVertex=1
optNormals=1
optTextureCoords=1
"""

with open(obj_settings_file, "w") as f:
    f.write(obj_settings_str)



# Some exported vrscenes refer to assets in the 3ds Max dir, and therefore these scenes
# are not portable, i.e., they will only render correctly on a machine with 3ds Max
# installed. To ensure that all of our exported scenes are portable, we copy all 3ds Max
# assets to the dataset_dir. After this copy step is complete, we still need to replace
# the paths to the 3ds Max dir in the exported vrscene file. We perform this path
# replacement during scene normalization.
current_source_file_path = path_utils.get_current_source_file_path(frame=inspect.currentframe())
in_max_sceneassets_photometric_dir  = _system_config.max_sceneassets_photometric_dir
out_max_sceneassets_photometric_dir = os.path.join(args.dataset_dir, "_asset", "sceneassets", "photometric")
distutils.dir_util.copy_tree(in_max_sceneassets_photometric_dir, out_max_sceneassets_photometric_dir) # can't use shutil.copytree because I want to overwrite files if they exist



current_source_file_path = path_utils.get_current_source_file_path(frame=inspect.currentframe())
dataset_dir              = os.path.abspath(args.dataset_dir)
tmp_dir                  = os.path.join(dataset_dir, "_tmp")

if not os.path.exists(tmp_dir): os.makedirs(tmp_dir)

maxbatch_bin_str          = _system_config.max_maxbatch_bin
_dataset_export_scenes_py = '"' + os.path.join(current_source_file_path, "_dataset_export_scenes.py") + '"'
log_str                   = '-log "' + os.path.join(tmp_dir, "_dataset_export_scenes_log.txt") + '"'
listener_log_str          = '-listenerlog "' + os.path.join(tmp_dir, "_dataset_export_scenes_listenerlog.txt") + '"'
dataset_dir_str           = '-mxsString dataset_dir:@"' + dataset_dir + '"'

if args.scene_names is not None:
    scene_names_str = '-mxsString scene_names:@"' + args.scene_names + '"'
else:
    scene_names_str = ''

cmd = \
    maxbatch_bin_str + \
    " " + _dataset_export_scenes_py + \
    " -v 5"                         + \
    " " + log_str                   + \
    " " + listener_log_str          + \
    " " + dataset_dir_str           + \
    " " + scene_names_str
print("")
print(cmd)
print("")

retval = subprocess.run(shlex.split(cmd)) # do not use os.system(...) because it doesn't parse command-line arguments cleanly
retval.check_returncode()



print("[HYPERSIM: DATASET_EXPORT_SCENES] Finished.")
