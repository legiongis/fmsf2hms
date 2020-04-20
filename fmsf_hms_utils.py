import os
import csv
import json
import time
import uuid
import logging
import processing
from datetime import datetime
from glob import glob
import urllib.request
from datetime import date
from osgeo import ogr
from dateutil.parser import parse
from qgis.PyQt.QtCore import QVariant
from qgis.core.additions.edit import edit
from qgis.core import QgsMessageLog, Qgis, QgsVectorLayer, QgsProject, QgsField
from qgis.utils import iface

DATADIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LOGDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

logger = logging.getLogger("fmsf2hms")


class FMSFDataset():

    def __init__(self, file_path, resource_type=""):

        self.file_path = file_path
        self.resource_type = resource_type
        self.layer_name = ""
        self.in_layer = None
        self.siteid_index = None
        self.out_layer = None
        self.out_layer_dp = None
        self.use_ids = []

        logger.debug(self.resource_type.upper())
        QgsMessageLog.logMessage(self.resource_type.upper(), "fmsf2hms")

        def initialize_layers():

            self.layer_name = os.path.splitext(os.path.basename(self.file_path))[0]
            self.in_layer = QgsVectorLayer(self.file_path, self.layer_name + " - FMSF", "ogr")

            # should implement this here instead:
            # QgsWkbTypes.displayString(gPnt.wkbType())
            geomtype = self.in_layer.wkbType()
            if geomtype == 1:
                geom_name = "Point"
            elif geomtype == 6 or geomtype == 3:
                geom_name = "MultiPolygon"
            else:
                # docs on this geom type are confusing. Good luck!
                # https://qgis.org/pyqgis/master/core/QgsWkbTypes.html
                msg = f"Failed: Unrecognized input geometry type: {geomtype}"
                logger.debug(msg)
                QgsMessageLog.logMessage(msg, "fmsf2hms")
                iface.messageBar().pushMessage("Error", msg, level=Qgis.Critical)
                return False

            self.siteid_index = self.in_layer.fields().names().index("SITEID")

            self.out_layer = QgsVectorLayer(geom_name, self.layer_name + " - New HMS", "memory",
                                            crs=self.in_layer.crs()
                                            )
            self.out_layer_dp = self.out_layer.dataProvider()
            self.out_layer_dp.addAttributes([i for i in self.in_layer.fields()])

            # add the extra OWNERSHIP field that will be populated separately
            self.out_layer_dp.addAttributes([QgsField("OWNERSHIP", QVariant.String)])
            self.out_layer.updateFields()

            msg = "layers initialized"
            logger.debug(msg)
            QgsMessageLog.logMessage(msg, "fmsf2hms")

        initialize_layers()

    def _get_export_configs(self):

        configs = {
            "date_fields": ["YEARESTAB", "D_NRLISTED", "YEARBUILT"],
            "concat_fields": {}
        }

        if self.resource_type == "Historic Cemetery":
            configs['concat_fields'] = {
                'CEMTYPE': ['CEMTYPE1', 'CEMTYPE2'],
                'ETHNICGRP': ['ETHNICGRP1', 'ETHNICGRP2', 'ETHNICGRP3', 'ETHNICGRP4']
            }

        if self.resource_type == "Historic Structure":
            configs['concat_fields'] = {
                'STRUCUSE': ['STRUCUSE1', 'STRUCUSE2', 'STRUCUSE3'],
                'STRUCSYS': ['STRUCSYS1', 'STRUCSYS2', 'STRUCSYS3'],
                'EXTFABRIC': ['EXTFABRIC1', 'EXTFABRIC2', 'EXTFABRIC3', 'EXTFABRIC4']
            }

        if self.resource_type == "Historic Structure":
            configs['concat_fields'] = {
                'SITETYPE': ['SITETYPE1', 'SITETYPE2', 'SITETYPE3', 'SITETYPE4', 'SITETYPE5', 'SITETYPE6'],
                'CULTURE': ['CULTURE1', 'CULTURE2', 'CULTURE3', 'CULTURE4', 'CULTURE5', 'CULTURE6', 'CULTURE7', 'CULTURE8']
            }

        return configs

    def add_input_to_map(self):
        QgsProject.instance().addMapLayer(self.in_layer)

    def add_output_to_map(self):
        QgsProject.instance().addMapLayer(self.out_layer)

    def compare_ids_against_hms(self, lookup, use_use_ids=False):

        msg = "comparing ids against HMS ids..."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")

        start = datetime.now()
        hms_siteids = [i[0] for i in lookup[self.resource_type]]

        if use_use_ids is True:
            self.use_ids = [i for i in self.use_ids if i not in hms_siteids]
        else:
            for feature in self.in_layer.getFeatures():
                siteid = feature.attributes()[self.siteid_index]
                if siteid not in hms_siteids:
                    self.use_ids.append(siteid)

        msg = f"  - done in {datetime.now() - start}. use_ids total: {len(self.use_ids)}"
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")

    def find_lighthouses(self):

        msg = "finding lighthouses..."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")

        start = datetime.now()
        for feature in self.in_layer.getFeatures():
            if "Lighthouse" in feature.attributes():
                self.use_ids.append(feature.attributes()[self.siteid_index])

        msg = f"  - done in {datetime.now() - start}. use_ids total: {len(self.use_ids)}"
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")

    def compare_to_shapefile(self):

        msg = "comparing to clip shapefile..."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")
        start = datetime.now()

        clip_shp = os.path.join(DATADIR, "structure_filter.gpkg")
        clipped = processing.run("native:clip", {
            'INPUT': self.in_layer,
            'OVERLAY': f'{clip_shp}|layername=structure_filter',
            'OUTPUT': 'TEMPORARY_OUTPUT'
        })['OUTPUT']

        for feature in clipped.getFeatures():
            siteid = feature.attributes()[self.siteid_index]
            self.use_ids.append(siteid)

        self.use_ids = list(set(self.use_ids))

        msg = f"  - done in {datetime.now() - start}. use_ids total: {len(self.use_ids)}"
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")

    def compare_to_idlist(self, csv_file):

        msg = "comparing to input siteid list..."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")
        start = datetime.now()

        with open(csv_file, newline="") as openf:
            reader = csv.DictReader(openf)
            for row in reader:
                self.use_ids.append(row['SITEID'])

        self.use_ids = list(set(self.use_ids))

        msg = f"  - done in {datetime.now() - start}. use_ids total: {len(self.use_ids)}"
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")

    def remove_destroyed_structures(self):

        msg = "removing destroyed structures..."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")
        start = datetime.now()

        des_structures = list()
        dfield = self.out_layer.fields().names().index("DESTROYED")
        for feature in self.in_layer.getFeatures():
            if feature.attributes()[dfield] == "YES":
                des_structures.append(feature.attributes()[self.siteid_index])
        currentids_set = set(self.use_ids)
        des_structures_set = set(des_structures)
        self.use_ids = list(currentids_set - des_structures_set)

        msg = f"  - done in {datetime.now() - start}. use_ids total: {len(self.use_ids)}"
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")

    def write_siteids_to_out_layer(self):

        msg = f"writing {len(self.use_ids)} use_ids to out_layer..."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")
        start = datetime.now()

        for feature in self.in_layer.getFeatures():
            siteid = feature.attributes()[self.siteid_index]
            if siteid in self.use_ids:
                self.out_layer_dp.addFeature(feature)

        self.out_layer.updateExtents()

        msg = f"  - done in {datetime.now() - start}."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")

        self.fix_geometry()

    def fix_geometry(self):

        msg = f"fixing geometries..."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")
        start = datetime.now()

        fixed_results = processing.run("native:fixgeometries", {
            'INPUT': self.out_layer,
            'OUTPUT': 'TEMPORARY_OUTPUT'
        })

        fixed_results['OUTPUT'].setName(self.out_layer.name())
        self.out_layer = fixed_results['OUTPUT']

        msg = f"  - done in {datetime.now() - start}."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")

    def add_owner_type(self, ownership_csv):

        msg = f"adding owner type to output layer..."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")
        start = datetime.now()

        owner_value_lookup = {
            'CITY': "City",
            'COUN': "County",
            'STAT': "State",
            'FEDE': "Federal",
            'PULO': "Local government",
            'PRIV': "Private-individual",
            'CORP': "Private-corporate-for profit",
            'CONP': "Private-corporate-nonprofit",
            'FORE': "Foreign",
            'NAAM': "Native American",
            'MULT': "Multiple categories of ownership",
            'UNSP': "Unspecified by surveyor",
            'PUUN': "Public-unspecified",
            'PRUN': "Private-unspecified",
            'OTHR': "Other",
            'UNKN': "Unknown"
        }

        owner_info = {}
        with open(ownership_csv, "r") as opencsv:
            reader = csv.DictReader(opencsv)
            for row in reader:
                siteid, owner = row['SiteID'].rstrip(), row['OwnType'].rstrip()
                if owner in owner_value_lookup:
                    owner_info[siteid] = owner_value_lookup[owner]
                elif owner in owner_value_lookup.values():
                    owner_info[siteid] = owner
                else:
                    msg = f" - siteid: {siteid}; unexpected ownership: {owner}"
                    logger.debug(msg)
                    QgsMessageLog.logMessage(msg, "fmsf2hms")

        own_field_index = self.out_layer.fields().names().index("OWNERSHIP")
        with edit(self.out_layer):
            for feature in self.out_layer.getFeatures():
                siteid = feature.attributes()[self.siteid_index]
                if siteid in owner_info:
                    feature["OWNERSHIP"] = owner_info[siteid]
                    self.out_layer.updateFeature(feature)

        msg = f"  - done in {datetime.now() - start}."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")

    def export_to_csv(self):

        msg = f"writing output layer to csv..."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")
        start = datetime.now()

        def parse_date(value):

            clean = ''.join(n for n in value if n.isdigit() or n in ['-', '/', '\\'])
            clean = clean.rstrip("-")
            if clean.rstrip() == "":
                return ""
            if len(clean) == 4:
                return "{}-01-01".format(clean)
            elif len(clean) > 4:
                try:
                    d = parse(clean)
                    return d.strftime("%Y-%m-%d")
                except:
                    msg = f"Unexpected date value (1) in {siteid}: {clean}"
                    logger.debug(msg)
                    QgsMessageLog.logMessage(msg, "fmsf2hms")
                    return ""
            else:
                msg = f"Unexpected date value (2) in {siteid}: {clean}"
                logger.debug(msg)
                QgsMessageLog.logMessage(msg, "fmsf2hms")
                return ""

        def sanitize_attributes(attributes, fnames, ex_configs):
            row = list()
            fields_to_concat = []
            concat_vals = {}
            for k, v in ex_configs['concat_fields'].items():
                concat_vals[k] = []
                fields_to_concat += v
            for index, attr in enumerate(attributes):
                fname = fnames[index]
                if str(attr) == "NULL":
                    value = ""
                else:
                    value = str(attr)

                if fname in config['date_fields']:
                    value = parse_date(value)

                if fname not in fields_to_concat:
                    row.append(value)
                    continue

                for k, v in ex_configs['concat_fields'].items():
                    if fname in v and not value == "":
                        concat_vals[k].append(value)

            new_concat = list(ex_configs['concat_fields'].keys())
            new_concat.sort()
            for nc in new_concat:
                row.append(";".join(concat_vals[nc]))
            return row

        config = self._get_export_configs()
        out_path = self.file_path.replace(".shp", "-hms.csv")
        field_names = self.out_layer.fields().names()
        fields = ['ResourceID', 'geom'] + field_names
        concat_fields = list()
        for new, orig in config['concat_fields'].items():
            concat_fields.append(new)
            fields = [i for i in fields if i not in orig]

        concat_fields.sort()
        fields += concat_fields

        with open(out_path, "w",  newline="") as outcsv:
            writer = csv.writer(outcsv)
            writer.writerow(fields)
            for feature in self.out_layer.getFeatures():
                id = str(uuid.uuid4())
                geom = feature.geometry().asWkt()
                featrow = sanitize_attributes(feature.attributes(), field_names, config)
                row = [id, geom] + featrow
                writer.writerow(row)

        msg = f"  - done in {datetime.now() - start}."
        logger.debug(msg)
        QgsMessageLog.logMessage(msg, "fmsf2hms")


def refresh_resource_lookup():

    QgsMessageLog.logMessage("beginning the refresh resource lookup", "fmsf2hms")
    hms_url = "https://hms.fpan.us/api/lookup"
    response = urllib.request.urlopen(hms_url)
    hms_resources = json.loads(response.read())

    outfilename = date.today().strftime("FMSF-HMS-lookup-table-%Y_%m_%d.csv")

    with open(os.path.join(DATADIR, outfilename), "w", newline="") as openf:
        writer = csv.writer(openf)
        writer.writerow(["type", "siteid", "resourceid"])
        for res in hms_resources['resources']:
            writer.writerow(res)


def get_lookup_table():

    csvs = glob(os.path.join(DATADIR, "*.csv"))
    if len(csvs) == 0:
        return None
    else:
        # return the last csv in the list: the most recent one based on date
        return csvs[-1]


def load_lookup():

    tablefile = get_lookup_table()
    if tablefile is None:
        iface.messageBar().pushMessage("Error", "Failed: You must first create the FMSF/HMS lookup table.", level=Qgis.Critical)
        return False

    with open(tablefile, "r") as openf:
        reader = csv.reader(openf)
        next(reader)
        data = [row for row in reader]

    lookup = {t: list() for t in set([i[0] for i in data])}
    for resource in data:
        type, siteid, resid = resource
        lookup[type].append((siteid, resid))

    return lookup
