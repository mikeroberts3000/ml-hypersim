import inspect
import itertools
import fnmatch
import os
from pymxs import runtime as rt

#
# can't import files from current dir by default, so duplicate path_utils here
#

import os, sys, inspect

def add_path_to_sys_path(path, mode, frame):
    assert mode == "unchanged" or mode == "relative_to_cwd" or mode == "relative_to_current_source_dir"
    if mode == "unchanged":
        if path not in sys.path:
            sys.path.insert(0,path)
    if mode == "relative_to_cwd":
        realpath = os.path.realpath(os.path.abspath(path))
        if realpath not in sys.path:
            sys.path.insert(0,realpath)
    if mode == "relative_to_current_source_dir":
        realpath = os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile(frame))[0],path)))
        if realpath not in sys.path:
            sys.path.insert(0,realpath)

def get_current_source_file_path(frame):
    return os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile(frame))[0])))

#
# define some useful utility functions
#

import MaxPlus

def _print(obj):
    string = str(obj)
    MaxPlus.Core.EvalMAXScript('logsystem.logEntry "' + string.replace('\\', '\\\\').replace('"', '\\"') + '" broadcast:true')

def _eval(string, silent=False):
    if not silent:
        _print("[HYPERSIM: _DATASET_EXPORT_SCENES] Executing MAXScript: " + string)
    return MaxPlus.Core.EvalMAXScript(string)



#
# parse command-line args
#

for k in rt.maxops.mxsCmdLineArgs.keys:
    _print('rt.maxops.mxsCmdLineArgs["' + k + '"] = ' + rt.maxops.mxsCmdLineArgs[k])

args_dataset_dir = rt.maxops.mxsCmdLineArgs[rt.name("dataset_dir")]

if rt.name("scene_names") in rt.maxops.mxsCmdLineArgs.keys:
    args_scene_names = rt.maxops.mxsCmdLineArgs[rt.name("scene_names")]
else:
    args_scene_names = None

assert os.path.exists(args_dataset_dir)

#
# parse dataset config
#

add_path_to_sys_path(args_dataset_dir, mode="relative_to_cwd", frame=inspect.currentframe())
import _dataset_config



_print("")
_print("")
_print("")
_print("[HYPERSIM: _DATASET_EXPORT_SCENES] Begin...")
_print("")
_print("")
_print("")



dataset_scenes_dir = os.path.join(args_dataset_dir, "scenes")

if args_scene_names is not None:
    scenes = [ s for s in _dataset_config.scenes if fnmatch.fnmatch(s["name"], args_scene_names) ]
else:
    scenes = _dataset_config.scenes



#
# disable VRay prompts
#

_eval('setVRaySilentMode()')

#
# export scenes
#

for s in scenes:

    # generate file names
    scene_name     = s["name"]
    scene_max_file = s["asset_file"] + ".max"
    scene_dir      = os.path.join(dataset_scenes_dir, scene_name)
    max_dir        = os.path.join(scene_dir, "_asset")
    max_export_dir = os.path.join(scene_dir, "_asset_export")

    max_file                             = os.path.join(max_dir, scene_max_file)
    metadata_cameras_max_export_csv_file = os.path.join(max_export_dir, "metadata_cameras_asset_export.csv")
    obj_file                             = os.path.join(max_export_dir, "scene.obj")
    vrscene_file                         = os.path.join(max_export_dir, "scene.vrscene")

    # create output dirs
    if not os.path.exists(max_export_dir): os.makedirs(max_export_dir)

    # loadMaxFile
    retval = _eval('loadMaxFile @"' + max_file + '" useFileUnits:true')
    if not retval.Get():
        _print("[HYPERSIM: _DATASET_EXPORT_SCENES] Failed to load " + max_file)
        assert False

    # export cameras
    with open(metadata_cameras_max_export_csv_file, "w") as f_cameras:

        f_cameras.write("camera_name\n")

        for ci in range(len(rt.cameras)):
        
            camera = rt.cameras[ci]
            if not "target" in camera.name.lower() and not "terget" in camera.name.lower():

                camera_name = "cam_" + camera.name

                _print("[HYPERSIM: _DATASET_EXPORT_SCENES] Exporting camera: " + camera_name)
                f_cameras.write(camera_name + "\n")

                camera_file = os.path.join(max_export_dir, camera_name + ".csv")

                with open(camera_file, "w") as f_camera:

                    f_camera.write(
                        "rotation_world_from_obj_00,rotation_world_from_obj_01,rotation_world_from_obj_02," + \
                        "rotation_world_from_obj_10,rotation_world_from_obj_11,rotation_world_from_obj_12," + \
                        "rotation_world_from_obj_20,rotation_world_from_obj_21,rotation_world_from_obj_22," + \
                        "translation_world_from_obj_x,translation_world_from_obj_y,translation_world_from_obj_z\n")

                    for ti in range(rt.animationRange.start, rt.animationRange.end+1):

                        # Note that we iterate in column-major order because 3ds Max returns the transpose of the R_world_from_cam matrix,
                        # where R_world_from_cam satisfies the equation: p_world == R_world_from_cam*p_cam for the camera space point p_cam
                        # and the world space point p_world.
                        for c,r in itertools.product(range(1,4),range(1,4)):
                            retval = _eval("at time " + str(ti) + " cameras[" + str(ci+1) + "].transform[" + str(r) + "][" + str(c) + "]", silent=True).Get()
                            f_camera.write("%.20f,"%retval)
                        for c in range(1,4):
                            retval = _eval("at time " + str(ti) + " cameras[" + str(ci+1) + "].transform[" + str(4) + "][" + str(c) + "]", silent=True).Get()
                            if c in range(1,3):
                                sep = ","
                            else:
                                sep = "\n"
                            f_camera.write("%.20f%s"%(retval,sep))

    # exportFile
    _eval('exportFile @"' + obj_file + '" #noprompt')

    # vrayExportRTScene
    _eval('vrayExportRTScene @"' + vrscene_file + '"')



_print("")
_print("")
_print("")
_print("[HYPERSIM: _DATASET_EXPORT_SCENES] Finished.")
_print("")
_print("")
_print("")
