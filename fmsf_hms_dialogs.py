# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FMSFToHMSDialog
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
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets

from .fmsf_hms_utils import get_lookup_table


# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS_CEM, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'dialog_cemetery.ui'))

FORM_CLASS_ARCH, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'dialog_archaeological_site.ui'))

FORM_CLASS_HIST, _ = uic.loadUiType(os.path.join(
        os.path.dirname(__file__), 'dialog_historic_structure.ui'))

FORM_CLASS_LOOKUP, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'dialog_update_lookup.ui'))

FORM_CLASS_WRITE, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'dialog_write_csv.ui'))


class CemeteryDialog(QtWidgets.QDialog, FORM_CLASS_CEM):

    def __init__(self, parent=None):
        """Constructor."""
        super(CemeteryDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)


class ArchaeologicalSiteDialog(QtWidgets.QDialog, FORM_CLASS_ARCH):
    def __init__(self, parent=None):
        """Constructor."""
        super(ArchaeologicalSiteDialog, self).__init__(parent)
        self.setupUi(self)


class HistoricStructureDialog(QtWidgets.QDialog, FORM_CLASS_HIST):
    def __init__(self, parent=None):
        """Constructor."""
        super(HistoricStructureDialog, self).__init__(parent)
        self.setupUi(self)


class UpdateLookupDialog(QtWidgets.QDialog, FORM_CLASS_LOOKUP):
    def __init__(self, parent=None):
        """Constructor."""
        super(UpdateLookupDialog, self).__init__(parent)
        self.setupUi(self)
        table = get_lookup_table()
        if table is None:
            msg1 = "No lookup table."
            msg2 = "Click OK to create the lookup table."
        else:
            msg1 = "Current lookup table: " + os.path.basename(table)
            msg2 = "Click OK to refresh the lookup table, or Cancel to continue using this one. "\
                   "There is no need to update the table if no new resources have been added to "\
                   "HMS since the date of the last table."

        self.lastUpdateLabel.setText(msg1)
        self.continueMessageLabel.setText(msg2)


class WriteCSVDialog(QtWidgets.QDialog, FORM_CLASS_WRITE):
    def __init__(self, parent=None):
        """Constructor."""
        super(WriteCSVDialog, self).__init__(parent)
        self.setupUi(self)
