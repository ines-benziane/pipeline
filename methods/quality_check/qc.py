import numpy as np

from mutools.io.orientation import set_orientation
from mutools.io.volume import asvolume
from mutools.utils.imageutils import volume_overview, draw_image
from mutools.utils.interpolate import interpolate_roi

def quality_check_volumes(volume):
    volume = set_orientation(volume, "RAI")
    image = volume_overview(volume)
    return image

def quality_check_seg(volume, roi, labels, step=1):
    """Produces frames for the GIF used for seg's QC.
    anat, roi = 3D volumes
    draw_image from mutools = expect 2D slice + labels, returns one image"""
    volume = set_orientation(volume, "RAI")
    roi = asvolume(roi.array, spacing=tuple(roi.spacing), origin=tuple(roi.origin),
                   transform=tuple(map(tuple, np.reshape(roi.transform, (3,3)).T)))
    roi = interpolate_roi(volume, roi)
    images = [draw_image(volume[:, :, k], roi = np.asarray(roi[:, :, k]), labels=labels, roialpha=0.5, show_labels=False) for k in  range (0,volume.shape[2], step)]
    return images

def save_gif(frames, path, duration=80):
    """Comple images into GIF. 
    
    Args:
    
    frames: images list given by quality_check_seg
    path: gif file path
    duration: in ms, time on screen of each frame. """
    frames = [f.convert("P") for f in frames]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=duration, loop=0)
