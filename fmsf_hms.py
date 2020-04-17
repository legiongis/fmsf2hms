# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FMSFToHMS
                                 A QGIS plugin
 This plugin is used to aid the processing and upload of FMSF data into HMS.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2020-04-01
        git sha              : $Format:%H$
        copyright            : (C) 2020 by Legion GIS, LLC
        email                : adam@legiongis.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
import logging
import processing
from datetime import datetime
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog
from qgis.core import QgsMessageLog, QgsLogger

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog boxes
from .fmsf_hms_dialogs import (
    CemeteryDialog,
    ArchaeologicalSiteDialog,
    HistoricStructureDialog,
    UpdateLookupDialog,
)

from .fmsf_hms_utils import refresh_resource_lookup, load_lookup
from .fmsf_hms_utils import FMSFDataset

def make_logger():
    LOGDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    logfile = os.path.join(LOGDIR, datetime.now().strftime("fmsf2hms_%Y-%m-%d.log"))

    logger = logging.getLogger("fmsf2hms")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(filename=logfile)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)

    if (len(logger.handlers) > 0):
        logger.handlers.clear()

    logger.addHandler(fh)

    return logger


class FMSFToHMS:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'FMSFToHMS_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&FMSF - HMS')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('FMSFToHMS', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
        self.add_action(
            os.path.join(icon_dir, "055-hat.png"),
            text=self.tr(u'Update FMSF/HMS Lookups'),
            callback=self.run_update_arches_lookup,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False
        )
        self.add_action(
            os.path.join(icon_dir, "017-ancient.png"),
            text=self.tr(u'Filter Cemeteries'),
            callback=self.run_cemeteries,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False
        )
        self.add_action(
            os.path.join(icon_dir, "015-pot.png"),
            text=self.tr(u'Filter Archaeological Sites'),
            callback=self.run_archaeological_sites,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False
        )
        self.add_action(
            os.path.join(icon_dir, "058-temple.png"),
            text=self.tr(u'Filter Historic Structures'),
            callback=self.run_historic_structures,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False
        )

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr(u'&FMSF - HMS'),
                action)
            self.iface.removeToolBarIcon(action)

    def select_input_shapefile(self):
        filename, _filter = QFileDialog.getOpenFileName(self.dlg, "Select input shapefile... ", "", "*.shp")
        self.dlg.shapefileInput.setText(filename)

    def select_ownership_csv(self):
        filename, _filter = QFileDialog.getOpenFileName(self.dlg, "Select owner type CSV... ", "", "*.csv")
        self.dlg.ownerTypeInput.setText(filename)

    def select_siteid_csv(self):
        filename, _filter = QFileDialog.getOpenFileName(self.dlg, "Select SITEID CSV... ", "", "*.csv")
        self.dlg.siteidInput.setText(filename)

    def run_cemeteries(self):
        """Run method that performs all the real work"""

        # initializes the logger, makes it available here, but also in the
        # fmsf_hms_utils operations by using logging.getLogger("fmsf2hms")
        logger = make_logger()

        self.dlg = CemeteryDialog()
        self.dlg.shapefileInputButton.clicked.connect(self.select_input_shapefile)
        self.dlg.ownerTypeInputButton.clicked.connect(self.select_ownership_csv)

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:

            input_file = self.dlg.shapefileInput.text().replace("'", "").replace('"', "")
            add_to_map = self.dlg.checkBoxAddInputLayer.isChecked()

            ownership_file = self.dlg.ownerTypeInput.text().replace("'", "").replace('"', "")

            lookup = load_lookup()

            ds = FMSFDataset(input_file, resource_type="Historic Cemetery")
            if add_to_map is True:
                ds.add_input_to_map()

            ds.compare_ids_against_hms(lookup)
            ds.write_siteids_to_out_layer()
            if os.path.isfile(ownership_file):
                ds.add_owner_type(ownership_file)
            ds.add_output_to_map()
            ds.export_to_csv()

    def run_archaeological_sites(self):
        """Run method that performs all the real work"""

        # initializes the logger, makes it available here, but also in the
        # fmsf_hms_utils operations by using logging.getLogger("fmsf2hms")
        logger = make_logger()

        self.dlg = ArchaeologicalSiteDialog()
        self.dlg.shapefileInputButton.clicked.connect(self.select_input_shapefile)
        self.dlg.ownerTypeInputButton.clicked.connect(self.select_ownership_csv)

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

        if result:

            input_file = self.dlg.shapefileInput.text().replace("'", "").replace('"', "")
            add_to_map = self.dlg.checkBoxAddInputLayer.isChecked()
            ownership_file = self.dlg.ownerTypeInput.text().replace("'", "").replace('"', "")

            lookup = load_lookup()

            ds = FMSFDataset(input_file, resource_type="Archaeological Site")
            if add_to_map is True:
                ds.add_input_to_map()
            ds.compare_ids_against_hms(lookup)
            ds.write_siteids_to_out_layer()
            if os.path.isfile(ownership_file):
                ds.add_owner_type(ownership_file)
            ds.add_output_to_map()
            ds.export_to_csv()

    def run_historic_structures(self):
        """Run method that performs all the real work"""

        # initializes the logger, makes it available here, but also in the
        # fmsf_hms_utils operations by using logging.getLogger("fmsf2hms")
        logger = make_logger()

        self.dlg = HistoricStructureDialog()
        self.dlg.shapefileInputButton.clicked.connect(self.select_input_shapefile)
        self.dlg.ownerTypeInputButton.clicked.connect(self.select_ownership_csv)
        self.dlg.siteidInputButton.clicked.connect(self.select_siteid_csv)

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

        if result:
            lookup = load_lookup()

            input_file = self.dlg.shapefileInput.text().replace("'", "").replace('"', "")
            add_to_map = self.dlg.checkBoxAddInputLayer.isChecked()
            ownership_file = self.dlg.ownerTypeInput.text().replace("'", "").replace('"', "")
            siteid_file = self.dlg.siteidInput.text().replace("'", "").replace('"', "")

            ds = FMSFDataset(input_file, resource_type="Historic Structure")
            if add_to_map is True:
                ds.add_input_to_map()

            ds.find_lighthouses()
            if os.path.isfile(siteid_file):
                ds.compare_to_idlist(siteid_file)
            ds.compare_to_shapefile()

            ds.compare_ids_against_hms(lookup, use_use_ids=True)
            ds.remove_destroyed_structures()
            ds.write_siteids_to_out_layer()
            if os.path.isfile(ownership_file):
                ds.add_owner_type(ownership_file)
            ds.add_output_to_map()
            ds.export_to_csv()

    def run_update_arches_lookup(self):
        """Run method that performs all the real work"""

        # initializes the logger, makes it available here, but also in the
        # fmsf_hms_utils operations by using logging.getLogger("fmsf2hms")
        logger = make_logger()

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        # if self.first_start == True:
        self.first_start = False
        self.dlg = UpdateLookupDialog()

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()

        if result:
            lookup = load_lookup()
            refresh_resource_lookup()
