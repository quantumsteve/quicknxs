from PyQt4 import QtGui, QtCore
from sf_calculator_interface import Ui_MainWindow
from run_sequence_breaker import RunSequenceBreaker
from mantid.simpleapi import *
from load_and_sort_nxsdata_for_sf_calculator import LoadAndSortNXSDataForSFcalculator
import numpy as np

class SFcalculator(QtGui.QMainWindow):
	
	_open_instances = []
	main_gui = None
	data_list = []
	big_table = None
	is_using_Si_slits = False
	loaded_list_of_runs = []
	
	def __init__(cls, main_gui, parent=None):
		cls.main_gui = main_gui
		QtGui.QMainWindow.__init__(cls)
		cls._open_instances.append(cls)
		cls.ui = Ui_MainWindow()
		cls.ui.setupUi(cls)
		
	def runSequenceLineEditEvent(cls):
		run_sequence = cls.ui.runSequenceLineEdit.text()
		oListRuns = RunSequenceBreaker(run_sequence)
		_new_runs = oListRuns.getFinalList()
		_old_runs = cls.loaded_list_of_runs
		_list_runs = np.unique(np.hstack([_old_runs, _new_runs]))
		o_load_and_sort_nxsdata = LoadAndSortNXSDataForSFcalculator(_list_runs)
		cls.big_table = o_load_and_sort_nxsdata.getTableData()
		cls.loaded_list_of_runs = o_load_and_sort_nxsdata.getListOfRunsLoaded()
		cls.is_using_Si_slits = o_load_and_sort_nxsdata.is_using_Si_slits
		cls.fillGuiTable()
		cls.ui.runSequenceLineEdit.setText("")
		
	def clearTable(cls):
		nbrRow = cls.ui.tableWidget.rowCount()
		if nbrRow > 0:
			for _row in range(nbrRow):
				cls.ui.tableWidget.removeRow(0)
		
	def fillGuiTable(cls):
		if cls.is_using_Si_slits:
			s2ih = 'SiH'
			s2iw = 'SiW'
		else:
			s2ih = 'S2H'
			s2iw = 'S2W'
		verticalHeader = ["Run #","Nbr. Attenuator",u"\u03bbmin(\u00c5)",
		                  u"\u03bbmax(\u00c5)",
		                  "Proton Charge (mC)",
		                  u"\u03bb requested (\u00c5)",
		                  "S1H","S1W",s2ih, s2iw]
		cls.ui.tableWidget.setHorizontalHeaderLabels(verticalHeader)

		cls.clearTable()
		_big_table = cls.big_table
		[nbr_row, nbr_column] = _big_table.shape
		for r in range(nbr_row):
			_row = _big_table[r,:]
			
			cls.ui.tableWidget.insertRow(r)
			
			_run_number = str(int(_row[0]))
			_item = QtGui.QTableWidgetItem(_run_number)
			cls.ui.tableWidget.setItem(r, 0, _item)
			
			_atte = int(_row[1])
			_widget = QtGui.QSpinBox()
			_widget.setMinimum(0)
			_widget.setMaximum(20)
			_widget.setValue(_atte)
			cls.ui.tableWidget.setCellWidget(r,1,_widget)
			
			_lambda_min = str(float(_row[2]))
			_item = QtGui.QTableWidgetItem(_lambda_min)
			cls.ui.tableWidget.setItem(r,2,_item)
			
			_lambda_max = str(float(_row[3]))
			_item = QtGui.QTableWidgetItem(_lambda_max)
			cls.ui.tableWidget.setItem(r,3,_item)
			
			_proton_charge = ("%.2e"%(float(_row[4])))
			_item = QtGui.QTableWidgetItem(_proton_charge)
			cls.ui.tableWidget.setItem(r,4,_item)
			
			_lambda_req = ("%.2f" %(float(_row[5])))
			_item = QtGui.QTableWidgetItem(_lambda_req)
			cls.ui.tableWidget.setItem(r,5,_item)
			
			_s1w = ("%.2f"%(float(_row[6])))
			_item = QtGui.QTableWidgetItem(_s1w)
			cls.ui.tableWidget.setItem(r,6,_item)
			
			_s1h = ("%.2f"%(float(_row[7])))
			_item = QtGui.QTableWidgetItem(_s1h)
			cls.ui.tableWidget.setItem(r,7,_item)

			_s2iw = ("%.2f"%(float(_row[8])))
			_item = QtGui.QTableWidgetItem(_s2iw)
			cls.ui.tableWidget.setItem(r,8,_item)

			_s2ih = ("%.2f"%(float(_row[9])))
			_item = QtGui.QTableWidgetItem(_s2ih)
			cls.ui.tableWidget.setItem(r,9,_item)
	