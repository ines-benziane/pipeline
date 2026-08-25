from mutools.io.orientation import set_orientation 
from mutools.utils.imageutils import volume_overview

def quality_check(volume):
    volume = set_orientation(volume, "RAI")
    image = volume_overview(volume)
    return image 