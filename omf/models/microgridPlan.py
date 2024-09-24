''' A model skeleton for future models: Calculates the sum of two integers. '''

import warnings
# warnings.filterwarnings("ignore")
import csv
import shutil, datetime
from pathlib import Path
import plotly
import plotly.graph_objs as go
import base64
from base64 import b64decode

# OMF imports
#from omf import feeder
#from omf.models.voltageDrop import drawPlot
from omf.models import __neoMetaModel__
from omf.models.__neoMetaModel__ import *

#import omf.solvers.reopt_jl as reopt
import omf.solvers.der_cam as dercam
import omf.solvers.PowerModelsONM as pmonm
import omf.solvers.protsetopt as pso

import omf.models.microgridDesign as microgridDesign


# Model metadata
modelName, template = __neoMetaModel__.metadata(__file__)
hidden = True

def work(modelDir, inputDict):
	''' Run the model in its directory. '''
	outData = {}
	run_reopt = inputDict.get("run_reopt")
	run_dercam = inputDict.get("run_dercam")
	run_pmonm = inputDict.get("run_pmonm")
	run_pso = inputDict.get("run_pso")
	outData["run_reopt"] = run_reopt
	outData["run_dercam"] = run_dercam
	outData["run_pmonm"] = run_pmonm
	outData["run_pso"] = run_pso

	#to figure out : which solvers can run in different threads/subprocesses?

	### reopt_jl
	if run_reopt:
		reoptInputs = inputDict.get("reopt_jl")
		reoptOutData = microgridDesign.work(modelDir,reoptInputs)
		outData["reoptOutData"] = reoptOutData 
	
	### der_cam	
	if run_dercam:
		dercamInputs = inputDict.get("dercam")
		apiKey = dercamInputs["api_key"]
		hasModelFile = dercamInputs["hasModelFile"]
		if hasModelFile:
			modelFile = dercamInputs["modelFile"]
			dercam.run(modelDir, modelFile=modelFile, apiKey=apiKey)
		else:
			dercam.run(modelDir, reoptFile="Scenario_Test_POST.json", apiKey=apiKey)
		dercamOutData = {}
		currentHeader = ""
		currentDict = {}
		with open(pJoin(modelDir,"results.csv")) as f:
			dercam_csv = csv.reader(f)
			for row in dercam_csv:
				# checks for header rows 
				if len(row) >= 1 and len(row[0]) > 1 and '+' in row[0]:
					if currentHeader != "" and currentDict != {}:
						dercamOutData[currentHeader] = currentDict
					currentHeader = row[0]
					remove_chars = '+ '
					for char in remove_chars:
						currentHeader = currentHeader.replace(char, '')
					currentDict = {}
				# adds key-value pair to currentDict otherwise
				elif len(row) > 1:
					val = row[0]
					val = val.replace(" ","")
					if len(row) == 2 or (len(row) == 3 and (row[2] == "NA" or row[1] == row[2])):
						currentDict[val] = row[1]
					else:
						currentDict[val] = row[1:]

		outData["dercamOutData"] = dercamOutData
		#plots/graphs to make:

	#to figure out: what data from reopt/dercam goes into pmonm?

	### PowerModelsONM
	if run_pmonm:
		pmonmInputs = inputDict.get("pmonm")
		if not pmonm.check_instantiated():
			pmonm.install_onm()
		pmonmCircuit = pmonmInputs.get("circuitFile")
		pmonmSettings = pmonmInputs.get("settingsFile")
		pmonmEvents = pmonmInputs.get("eventsFile")
		if pmonmSettings == "":
			settingsInputs = pmonmInputs.get("settingsInputs")
			settingsPath = pJoin(modelDir,"pmonm_settings.json")
			settingsInputs["settingsPath"] = settingsPath
			settingsInputs["circuitPath"] = pmonmCircuit
			pmonm.build_settings_file(**settingsInputs)
		else:
			settingsPath = pmonmSettings
		if pmonmEvents == "":
			eventsInputs = pmonmInputs.get("eventsInputs")
			eventsPath = pJoin(modelDir,"pmonm_events.json")
			eventsInputs["eventsPath"] = eventsPath
			eventsInputs["circuitPath"] = pmonmCircuit
			pmonm.build_events_file(**eventsInputs)
		else:
			eventsPath = pmonmEvents
		pmonmOut = pJoin(modelDir,"pmonm_output.json")
		pmonm.run_onm(circuitPath=pmonmCircuit, settingsPath=settingsPath, eventsPath=eventsPath, outputPath=pmonmOut)
		with open(pmonmOut) as j:
			pmonmOutData = json.load(j)
		outData["pmonmOutData"] = pmonmOutData

	#to figure out: how to parse pmonm "Protection Settings" output into pso 
	# => convert to dss file somehow? not needed?
	
	### ProtectionSettingsOptimizer
	if run_pso:
		psoInputs = inputDict.get("pso")
		del psoInputs["circuitFile"]
		psoInputs["testPath"] = psoInputs["circuitPath"]
		psoInputs["testFile"] = psoInputs["circuitFileName"]
		del psoInputs["circuitPath"]
		del psoInputs["circuitFileName"]
		pso.run_pso(**psoInputs)
		with open(pJoin(psoInputs["testPath"],"settings_rso_out.json")) as j:
			psoSettings = json.load(j)
		with open(pJoin(psoInputs["testPath"],"old_info_rso_out.json")) as j:
			psoOldInfo = json.load(j)
		outData["psoSettings"] = psoSettings
		outData["psoOldInfo"] = psoOldInfo
		with open(pJoin(psoInputs["testPath"],"pso_plot.png"),"rb") as inFile:
			outData["psoPlotImg"] = base64.standard_b64encode(inFile.read()).decode()
		with open(pJoin(psoInputs["testPath"],"fitness_plot.png"),"rb") as inFile:
			outData["fitnessPlotImg"] = base64.standard_b64encode(inFile.read()).decode()

	if run_pmonm:
		#making PowerModelsONM output graphs :
		#todo: outData["Protection settings"]["settings"] should contain key output (not showing anything with current test files)
		def makeGridLine(x,y,color,name):
				plotLine = go.Scatter(
					x = x, 
					y = y,
					line = dict( color=(color)),
					name = name,
					hoverlabel = dict(namelength = -1),
					showlegend=True
				)
				return plotLine
		
		plotlyLayout = go.Layout(
				width=1000,
				height=375,
				legend=dict(
					x=0,
					y=1.25,
					orientation="h")
				)
		
		x = outData['pmonmOutData']['Simulation time steps']
		plotData = []
		pmonm_voltages = outData["pmonmOutData"]["Voltages"]
		min_voltage = makeGridLine(x, pmonm_voltages["Min voltage (p.u.)"],'blue','Min. Voltage')
		plotData.append(min_voltage)
		max_voltage = makeGridLine(x, pmonm_voltages["Max voltage (p.u.)"],'red','Max. Voltage')
		plotData.append(max_voltage)
		mean_voltage = makeGridLine(x, pmonm_voltages["Mean voltage (p.u.)"],'green','Mean Voltage')
		plotData.append(mean_voltage)
		plotlyLayout['yaxis'].update(title='Voltage (p.u.)')
		plotlyLayout['xaxis'].update(title='Simulation Time Steps')
		outData["pmonmVoltageData"] = json.dumps(plotData, cls=plotly.utils.PlotlyJSONEncoder)
		outData["pmonmVoltageLayout"] = json.dumps(plotlyLayout, cls=plotly.utils.PlotlyJSONEncoder)

		plotData = []
		storage_soc = makeGridLine(x, outData['pmonmOutData']['Storage SOC (%)'],'red','Storage SOC')
		plotData.append(storage_soc)
		plotlyLayout['yaxis'].update(title='SOC (%)')
		plotlyLayout['xaxis'].update(title='Simulation Time Steps')
		outData["pmonmStorageSOCData"] = json.dumps(plotData, cls=plotly.utils.PlotlyJSONEncoder)
		outData["pmonmStorageSOCLayout"] = json.dumps(plotlyLayout, cls=plotly.utils.PlotlyJSONEncoder)

		pmonm_load_served = outData['pmonmOutData']['Load served']
		plotData = []
		totalLoad = makeGridLine(x,pmonm_load_served['Total load (%)'],'purple','Total load')
		plotData.append(totalLoad)
		bonusLoadViaMicrogrid = makeGridLine(x,pmonm_load_served['Bonus load via microgrid (%)'],'brown','Bonus load via microgrid')
		plotData.append(bonusLoadViaMicrogrid)
		feederLoad = makeGridLine(x,pmonm_load_served['Feeder load (%)'],'red','Feeder load')
		plotData.append(feederLoad)
		microgridLoad = makeGridLine(x,pmonm_load_served['Microgrid load (%)'],'gray','Microgrid load')
		plotData.append(microgridLoad)
		plotlyLayout['yaxis'].update(title='Load Served (%)')
		plotlyLayout['xaxis'].update(title='Simulation Time Steps')
		outData["pmonmLoadServedData"] = json.dumps(plotData, cls=plotly.utils.PlotlyJSONEncoder)
		outData["pmonmLoadServedLayout"] = json.dumps(plotlyLayout, cls=plotly.utils.PlotlyJSONEncoder)

		plotData = []
		microgridCustomers = makeGridLine(x,pmonm_load_served['Microgrid customers (%)'],'blue','Microgrid customers')
		plotData.append(microgridCustomers)
		feederCustomers = makeGridLine(x,pmonm_load_served['Feeder customers (%)'],'yellow','Feeder customers')
		plotData.append(feederCustomers)
		totalCustomers = makeGridLine(x,pmonm_load_served['Total customers (%)'],'green','Total customers')
		plotData.append(totalCustomers)
		bonusCustomersViaMicrogrid = makeGridLine(x,pmonm_load_served['Bonus customers via microgrid (%)'],'orange','Bonus customers via microgrid (%)')
		plotData.append(bonusCustomersViaMicrogrid)
		plotlyLayout['yaxis'].update(title='Customers (%)')
		plotlyLayout['xaxis'].update(title='Simulation Time Steps')
		outData["pmonmCustomersData"] = json.dumps(plotData, cls=plotly.utils.PlotlyJSONEncoder)
		outData["pmonmCustomersLayout"] = json.dumps(plotlyLayout, cls=plotly.utils.PlotlyJSONEncoder)

		pmonm_generator_profiles = outData['pmonmOutData']["Generator profiles"]
		plotData = []
		diesel_dg = makeGridLine(x,pmonm_generator_profiles['Diesel DG (kW)'],'red','Diesel DG')
		plotData.append(diesel_dg)
		energy_storage = makeGridLine(x,pmonm_generator_profiles['Energy storage (kW)'],'green','Energy storage')
		plotData.append(energy_storage)
		solar_dg = makeGridLine(x,pmonm_generator_profiles['Solar DG (kW)'],'orange','Solar DG')
		plotData.append(solar_dg)
		grid_mix = makeGridLine(x,pmonm_generator_profiles['Grid mix (kW)'],'blue','Grid mix')
		plotData.append(grid_mix)
		plotlyLayout['yaxis'].update(title='kW')
		plotlyLayout['xaxis'].update(title='Simulation Time Steps')
		outData["pmonmGeneratorProfilesData"] = json.dumps(plotData, cls=plotly.utils.PlotlyJSONEncoder)
		outData["pmonmGeneratorProfilesLayout"] = json.dumps(plotlyLayout, cls=plotly.utils.PlotlyJSONEncoder)

		#to potentially add: "Device action timeline"

	#outData["output"] = 
	# Model operations typically ends here.
	# Stdout/stderr.
	outData["stdout"] = "Success"
	outData["stderr"] = ""
	return outData

def new(modelDir):
	''' Create a new instance of this model. Returns true on success, false on failure. '''
	defaultInputs = {
		"user" : "admin",
		"modelType": modelName,
		"created":str(datetime.datetime.now()),
		"run_reopt": True,
		"run_dercam": False,
		"run_pmonm": True,
		"run_pso": True
	}

	#saving solvers' default inputs to sub-dictionaries in defaultInputs
 
	##### reopt_jl
	fName = "loadShape.csv"
	with open(pJoin(omf.omfDir, "static", "testFiles", "lehigh4mgs", fName)) as f:
		load_shape = f.read()
	cfName = "criticalLoadShape.csv"
	with open(pJoin(omf.omfDir, "static", "testFiles", "lehigh4mgs", cfName)) as f:
		crit_load_shape = f.read()
	#updated to microgridup/data/projects/lehigh4mgs/reopt_3mg/allInputData.json > REOPT_INPUTS
	with open(pJoin(omf.omfDir, "static", "testFiles", "lehigh4mgs", "allInputData.json")) as jsonFile:
		reoptDefaultInputs = json.load(jsonFile)

	reoptDefaultInputs["loadShape"] = load_shape
	reoptDefaultInputs["criticalLoadShape"] = crit_load_shape
	reoptDefaultInputs["fileName"] = fName
	reoptDefaultInputs["criticalFileName"] = cfName

	defaultInputs["reopt_jl"] = reoptDefaultInputs
	
	### DER-CAM
	dercamInputs = {
		"api_key": "",
		"hasModelFile": True, #False,
		"modelFile": pJoin(__neoMetaModel__._omfDir, "solvers","der_cam","testFiles","test.xlsx"),
		"modelFileName": "test.xlsx"
	}
	defaultInputs["dercam"] = dercamInputs
 
 	### PowerModelsONM
	settingsInputs = {
			"loadPrioritiesFile": "",
			"microgridTaggingFile": "",
			"max_switch_actions": 1,
			"vm_lb_pu": 0.9,
			"vm_ub_pu": 1.1,
			"sbase_default": 1000.0,
			"line_limit_mult":'Inf',
			"vad_deg":5.0, 
	}
	eventsInputs = {
			"custom_events_file":'',
			"default_switch_state": 'PMD.OPEN',
			"default_switch_dispatchable": 'PMD.NO',
			"default_switch_status": 'PMD.ENABLED'
	}
	#defaults for pmonm - using while lehigh not working
	defaultPath = pJoin(__neoMetaModel__._omfDir, "static", "testFiles")
	defaultCircuitFile = "iowa240_dwp_22.dss"
	defaultSettingsFile = "iowa240_dwp_22.settings.json"
	defaultEventsFile = "iowa240_dwp_22.events.json"
	#lehigh test files - working for pso but not pmonm currently
	circuitPath = pJoin(__neoMetaModel__._omfDir, "static", "testFiles","lehigh4mgs")
	#circuit_plus_mgAll_relays.dss -> 8760-element loadshapes
	#circuit_plus_mgAll_relays_new.dss -> 24-element loadshapes
	#circuit_plus_mgAll_relays_df.dss -> edits by david fobes - also 24-element loadshapes
	circuitFile = "circuit_plus_mgAll_relays_df.dss" 
	settingsFile =  "circuit_plus_mgAll_relays.settings.json"
	eventsFile =  "circuit_plus_mgAll_relays.events.json"
	pmonmDefaultInputs = {
		"circuitFile": pJoin(circuitPath,circuitFile),
		"circuitFileName": circuitFile,
		#todo: on switch (T/F) display settings/eventsFile option (False) or settings/events file parameters (True)
		"buildSettingsFile": False, 
		"buildEventsFile": False,
		"settingsFile": pJoin(circuitPath, settingsFile), #"",
		"settingsFileName": settingsFile, #"",
		"eventsFile": pJoin(circuitPath,eventsFile),
		"eventsFileName": eventsFile,
		"loadPrioritiesFileName": "",
		"microgridTaggingFileName": "",
		"settingsInputs": settingsInputs,
		"custom_events_file_name": "",
		"eventsInputs": eventsInputs
	}
	defaultInputs["pmonm"] = pmonmDefaultInputs 

	### ProtectionSettingsOptimizer
	defaultpsoPath = pJoin(__neoMetaModel__._omfDir,"solvers","protsetopt","testFiles")
	defaultpsoFile = pJoin(defaultpsoPath,"IEEE34Test.dss")
	defaultpsoFileName = "IEEE34Test.dss"
	#above test paths/files not used since lehigh working for pso 
	psoDefaultInputs = { 
		"circuitPath": circuitPath,
		"circuitFile": pJoin(circuitPath,circuitFile),
		"circuitFileName": circuitFile,
		"Fres": ['0.001','1'], #fault resistances to test
		"Fts": ['3ph','SLG','LL'], #supported fault types
		"Force_NOIBR": 1, 
		"enableIT": 0,
		"CTI": 0.25,
        "OTmax": 10,
		"type_select": False,
		"Fault_Res": ['R0_001','R1'],
		"Min_Ip": [0.1,0.1],
		"Substation_bus": 'sourcebus'
	}
	defaultInputs["pso"] = psoDefaultInputs 

	return __neoMetaModel__.new(modelDir, defaultInputs)

def display_prev_results():
	modelLoc = Path(__neoMetaModel__._omfDir,"data","Model","admin","Automated Testing of " + modelName)
	__neoMetaModel__.renderAndShow(modelLoc)

@neoMetaModel_test_setup
def _debugging():
	# Location
	modelLoc = Path(__neoMetaModel__._omfDir,"data","Model","admin","Automated Testing of " + modelName)
	# Blow away old test results if necessary.
	try:
		shutil.rmtree(modelLoc)
	except:
		# No previous test results.
		pass
	# Create New.
	new(modelLoc)
	# Pre-run.
	__neoMetaModel__.renderAndShow(modelLoc)
	# Run the model.
	__neoMetaModel__.runForeground(modelLoc)
	# Show the output.
	__neoMetaModel__.renderAndShow(modelLoc)

if __name__ == '__main__':
	_debugging()
	#display_prev_results()
