from osgeo import gdal, osr
from mapproxy.proj import Proj, transform
from mapproxy.srs import get_epsg_num
import uuid

def get_geotransform(size, bbox):
    print bbox
    resx = (bbox[2] - bbox[0]) / float(size[0])
    resy = (bbox[3] - bbox[1]) / float(size[1])
    return (bbox[0], resx, 0.0, bbox[3], 0.0, -resy)

def georeference(image, buffer, srs, bbox):
    source_temp_name = '/vsimem/{}.tif'.format(uuid.uuid4())
    gdal.FileFromMemBuffer(source_temp_name, buffer.read())
    source_dataset = gdal.Open(source_temp_name)

    destination_temp_name = '/vsimem/{}.tif'.format(uuid.uuid4())
    driver = gdal.GetDriverByName("GTiff")
    destination_dataset = driver.CreateCopy(destination_temp_name, source_dataset, 0)

    gt = get_geotransform(image.size, bbox)
    destination_dataset.SetGeoTransform(gt)
    srs2 = osr.SpatialReference()
    srs2.ImportFromEPSG(get_epsg_num(srs.srs_code))
    srs_as_wkt = srs2.ExportToWkt()
    destination_dataset.SetProjection(srs_as_wkt)

    source_dataset = None
    destination_dataset = None

    f = gdal.VSIFOpenL(destination_temp_name, 'rb')
    gdal.VSIFSeekL(f, 0, 2) # seek to end
    size = gdal.VSIFTellL(f)
    gdal.VSIFSeekL(f, 0, 0) # seek to beginning
    georeferenced_buffer = gdal.VSIFReadL(1, size, f)
    gdal.VSIFCloseL(f)

    gdal.Unlink(source_temp_name)
    gdal.Unlink(destination_temp_name)
    
    return georeferenced_buffer