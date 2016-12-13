import yaml
import sqlite3
import os

def conf_from_geopackage(geopackage_file, output_file=None):
    conf = get_geopackage_configuration_dict(geopackage_file)
    yaml.SafeDumper.add_representer(
        type(None),
        lambda dumper, value: dumper.represent_scalar(u'tag:yaml.org,2002:null', '')
    )

    if output_file:
        with open('data.yml', 'w') as outfile:
            outfile.write(yaml.safe_dump(conf, default_flow_style=False))
    else:
        print(yaml.safe_dump(get_geopackage_configuration_dict(geopackage_file),default_flow_style=False))


def get_gpkg_contents(geopackage_file, data_type='tiles'):
    """
    :param geopackage_file: Path to the geopackage file.
    :param data_type: The type of layer to return tiles or features.
    :return: One or more tuples with the table_name, min_x, min_y, max_x, max_y, srs_id for each layer in the geopackage.
    """
    with sqlite3.connect(geopackage_file) as db:
        cur = db.execute("SELECT table_name, data_type, identifier, description, last_change, min_x, min_y, max_x, "
                             "max_y, srs_id "
                             "FROM gpkg_contents WHERE data_type = ?", (data_type,))
    return cur.fetchall()


def get_table_organization_coordsys_id(geopackage_file, srs_id):
    """
    :param geopackage_file: Path to the geopackage file.
    :param srs_id: The srs_id which is the key value in the organization_coordsys_id.
    :return: An integer representing the organization_coordsys_id as an EPSG code.
    """
    with sqlite3.connect(geopackage_file) as db:
        cur = db.execute("SELECT organization_coordsys_id FROM gpkg_spatial_ref_sys WHERE srs_id = ?"
                             , (srs_id,))
    results = cur.fetchone()
    if results:
        return results[0]


def get_table_tile_matrix(geopackage_file, table_name):
    """
    :param geopackage_file: Path to the geopackage file.
    :param table_name: The table_name associated with the tile_matrix data.
    :return: A tuple of tuple containing zoom_level, matrix_width, matrix_height, tile_width, tile_height, pixel_x_size,
    pixel_y_size for each zoom_level.
    """

    with sqlite3.connect(geopackage_file) as db:
        cur = db.execute("SELECT zoom_level,"
                             "matrix_width, "
                             "matrix_height, "
                             "tile_width, "
                             "tile_height, "
                             "pixel_x_size, "
                             "pixel_y_size "
                             "FROM gpkg_tile_matrix WHERE table_name = ?"
                             "ORDER BY zoom_level", (table_name,))
        return cur.fetchall()


def get_estimated_tile_res_ratio(tile_matrix):
    """

    :param tile_matrix: A tuple of tuples representing the geopackage tile matrix (without the table name included).
    :return: The rate at which the resolution increases between levels.
    """
    default_res_factor = 2
    if len(tile_matrix) < 2:
        return default_res_factor
    layer = tile_matrix[0]
    next_layer = tile_matrix[1]
    return (layer[6]/next_layer[6])/(next_layer[0]-layer[0])


def get_res_table(tile_matrix):
    res_ratio = get_estimated_tile_res_ratio(tile_matrix)
    res_table = []
    if tile_matrix[0][0] == 0:
        first_level_res = tile_matrix[0][5]
    else:
        first_level_res = tile_matrix[0][5]*(res_ratio**tile_matrix[0][0])
    tile_matrix_set = {}
    for level in tile_matrix:
        tile_matrix_set[level[0]] = level
    if not tile_matrix_set.get(0):
        res_table += [first_level_res]
    else:
        res_table += [tile_matrix_set.get(0)[5]]
    for level in range(1, 19):
        res = tile_matrix_set.get(level)
        if not res:
            res_table += [first_level_res/(res_ratio**level)]
        else:
            res_table += [res[5]]
    return res_table


def get_geopackage_configuration_dict(geopackage_file):
    gpkg_contents = get_gpkg_contents(geopackage_file, data_type='tiles')
    conf = {'grids': {},
            'caches': {},
            'layers': [],
            'services': {'demo': None,
                         'tms': {'use_grid_names': True, 'origin': 'nw'},
                         'kml': {'use_grid_names': True},
                         'wmts': None,
                         'wms': None}}

    for gpkg_content in gpkg_contents:
        table_name = str(gpkg_content[0])
        tile_matrix = get_table_tile_matrix(geopackage_file, table_name)
        srs = get_table_organization_coordsys_id(geopackage_file, gpkg_content[9])
        if not tile_matrix or not srs:
            continue
        conf['grids']['{0}_{1}'.format(table_name, srs)] = {'srs': 'EPSG:{0}'.format(srs),
                                                          'tile_size': [tile_matrix[0][3], tile_matrix[0][4]],
                                                          'bbox': [gpkg_content[5],
                                                                   gpkg_content[6],
                                                                   gpkg_content[7],
                                                                   gpkg_content[8]],
                                                          'res': get_res_table(tile_matrix),
                                                          'origin': 'nw'}
        conf['caches']['{0}_cache'.format(table_name)] = {'sources': [],
                                                         'grids': ['{0}_{1}'.format(table_name, srs)],
                                                         'cache': {'type': 'geopackage',
                                                                   'filename': os.path.abspath(geopackage_file),
                                                                   'table_name': table_name}}
        conf['layers'] += [{'name': table_name, 'title': table_name, 'sources': ['{0}_cache'.format(table_name)]}]
    return conf
