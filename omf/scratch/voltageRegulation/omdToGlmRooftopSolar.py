import json, math, os, argparse
from omf import feeder
from os.path import join as pJoin
import pandas as pd
import numpy as np
import csv
import omf
from models.voltageDrop import drawPlot
import re
from datetime import datetime


def ConvertAndwork(filePath):
	#Converts omd to glm, adds in necessary recorder, collector, and attributes+parameters for gridballast gld to run on waterheaters and ziploads
	with open(filePath, 'r') as inFile:
		inFeeder = json.load(inFile)
		inFeeder['tree'][u'01'] = {u'omftype': u'#include', u'argument': u'"hot_water_demand1.glm"'}
		inFeeder['tree'][u'011'] = {u'class': u'player', u'double': u'value'}# add in manually for now
		name_volt_dict ={}
		solar_meters=[]
		wind_obs=[]
		substation = None 
		rooftopSolars = []
		rooftopInverters =[]
		for key, value in inFeeder['tree'].iteritems():
			if 'name' in value and 'solar' in value['name']:
				inverter_ob = value['parent']
				for key, value in inFeeder['tree'].iteritems():
					if 'name' in value and value['name']==inverter_ob:
						solar_meters.append(value['parent'])
			if 'name' in value and 'wind' in value['name']:
				wind_obs.append(value['name'])
			if 'name' in value and 'nominal_voltage' in value:
				name_volt_dict[value['name']] = {'Nominal_Voltage': value['nominal_voltage']}
			if 'object' in value and (value['object'] == 'waterheater'):
				inFeeder['tree'][key].update({'heat_mode':'ELECTRIC'})
				inFeeder['tree'][key].update({'enable_volt_control':'false'})
				inFeeder['tree'][key].update({'volt_lowlimit':'113.99'})
				inFeeder['tree'][key].update({'volt_uplimit':'126.99'}) 
			if'object' in value and (value['object']== 'ZIPload'):
				inFeeder['tree'][key].update({'enable_volt_control':'false'})
				inFeeder['tree'][key].update({'volt_lowlimit':'113.99'})
				inFeeder['tree'][key].update({'volt_uplimit':'126.99'})
			if 'object' in value and (value['object']== 'house'):
				houseMeter = value['parent']
				houseName = value['name']
				houseLon = value['longitude']
				houseLat = value['latitude']
				rooftopSolar_inverter = houseName+"_rooftop_inverter;"
				rooftopSolars.append("object solar {\n\tname "+houseName+"_rooftopSolar;\n\tparent "+rooftopSolar_inverter+"\n\tgenerator_status ONLINE;\n\tefficiency 0.2;\n\tlongitude "+houseLon+";\n\tgenerator_mode SUPPLY_DRIVEN;\n\tpanel_type SINGLE_CRYSTAL_SILICON;\n\tlatitude "+houseLat+";\n\tarea 500;\n\t};\n")
				rooftopInverters.append("object inverter {\n\tphases ABCN;\n\tpower_factor 1.0;\n\tname "+rooftopSolar_inverter+"\n\tparent "+houseMeter+";\n\tinverter_type PWM;\n\tlongitude "+houseLon+";\n\tgenerator_mode CONSTANT_PF;\n\tlatitude "+houseLat+";\n\t};\n")
			if 'argument' in value and ('minimum_timestep' in value['argument']):
					interval = int(re.search(r'\d+', value['argument']).group())
			if 'bustype' in value and 'SWING' in value['bustype']:
				substation = value['name']
				value['object'] = 'meter'
		collectorwat=("object collector {\n\tname collector_Waterheater;\n\tgroup class=waterheater;\n\tproperty sum(actual_load);\n\tinterval "+str(interval)+";\n\tfile measured_load_waterheaters.csv;\n};\n")
		collectorz=("object collector {\n\tname collector_ZIPloads;\n\tgroup class=ZIPload;\n\tproperty sum(base_power);\n\tinterval "+str(interval)+";\n\tfile measured_load_ziploads.csv;\n};\n")
		collectorh=("object collector {\n\tname collector_HVAC;\n\tgroup class=house;\n\tproperty sum(heating_demand), sum(cooling_demand);\n\tinterval "+str(interval)+";\n\tfile measured_HVAC.csv;\n};\n")
		# Measure powerflow over Triplex meters, this will determine if solar is generating power. Negative powerflow means solar is generating. Positive means no. 
		collectorRoof=("object collector {\n\tname collector_rooftop;\n\tgroup class=triplex_meter;\n\tproperty sum(measured_real_power);\n\tinterval "+str(interval)+";\n\tfile measured_load_triplex.csv;\n};\n")

		recordersub=("object recorder {\n\tinterval "+str(interval)+";\n\tproperty measured_real_power;\n\tfile measured_substation_power.csv;\n\tparent "+str(substation)+";\n\t};\n")
		recorderSolarRoof = ("object recorder {\n\tinterval "+str(interval)+";\n\tproperty measured_real_power;\n\tfile measured_standard_solar_roof.csv;\n\tparent nreca_synthetic_meter_11922;\n\t};\n")
		recorders = []
		recorderw=[]
		for i in range(len(solar_meters)):
			recorders.append(("object recorder {\n\tinterval "+str(interval)+";\n\tproperty measured_real_power;\n\tfile measured_solar_"+str(i)+".csv;\n\tparent "+str(solar_meters[i])+";\n\t};\n"))
		for i in range(len(wind_obs)):
			recorderw.append(("object recorder {\n\tinterval "+str(interval)+";\n\tproperty Pconv;\n\tfile measured_wind_"+str(i)+".csv;\n\tparent "+str(wind_obs[i])+";\n\t};\n"))

	with open('outGLMtest_rooftop.glm', "w") as outFile:
		addedString = collectorwat+collectorz+collectorh+recordersub+collectorRoof+recorderSolarRoof
		for i in recorders:
			addedString = addedString+i
		for i in recorderw:
			addedString = addedString + i
		for i, j in zip(rooftopInverters, rooftopSolars):
			addedString = addedString + i + j
		outFile.write(feeder.sortedWrite(inFeeder['tree'])+addedString)


	os.system(omf.omfDir +'/solvers/gridlabd_gridballast/local_gd/bin/gridlabd outGLMtest_rooftop.glm')

	return name_volt_dict

def ListOffenders(name_volt_dict):
	#Finds objects that carry too much voltage, these are called 'Offenders', write to disk
	data = pd.read_csv(('voltDump.csv'), skiprows=[0])
	for i, row in data['voltA_real'].iteritems():
		voltA_real = data.loc[i,'voltA_real']
		voltA_imag = data.loc[i,'voltA_imag']
		voltA_mag = np.sqrt(np.add((voltA_real*voltA_real), (voltA_imag*voltA_imag)))
		name_volt_dict[data.loc[i, 'node_name']].update({'Volt_A':voltA_mag})
		voltB_real = data.loc[i,'voltB_real']
		voltB_imag = data.loc[i,'voltB_imag']
		voltB_mag = np.sqrt(np.add((voltB_real*voltB_real), (voltB_imag*voltB_imag)))
		name_volt_dict[data.loc[i, 'node_name']].update({'Volt_B':voltB_mag})
		voltC_real = data.loc[i,'voltC_real']
		voltC_imag = data.loc[i,'voltC_imag']
		voltC_mag = np.sqrt(np.add((voltC_real*voltC_real), (voltC_imag*voltC_imag)))
		name_volt_dict[data.loc[i, 'node_name']].update({'Volt_C':voltC_mag})
	offenders = []
	offendersGen = []
	for name, volt in name_volt_dict.iteritems():
		if name in data['node_name'].values:
			if (float(volt['Volt_A'])/float(volt['Nominal_Voltage'])) > 1.05:
				offenders.append(tuple([name, float(volt['Volt_A'])/float(volt['Nominal_Voltage'])]))
				offendersGen.append(name)
			if (float(volt['Volt_B'])/float(volt['Nominal_Voltage'])) > 1.05:
				offenders.append(tuple([name, float(volt['Volt_B'])/float(volt['Nominal_Voltage'])]))
				offendersGen.append(name)
			if (float(volt['Volt_C'])/float(volt['Nominal_Voltage'])) > 1.05:
				offenders.append(tuple([name, float(volt['Volt_C'])/float(volt['Nominal_Voltage'])]))
				offendersGen.append(name)



	#Print General information about offending nodes
	offenders = list(set(offenders))
	# print len(offenders)
	isum = 0
	offendersNames = []
	for i in range(len(offenders)):
		isum = isum + offenders[i][1]
		offendersNames.append(offenders[i][0])
	offendersGen = list(set(offendersGen))
	# print ("average voltage overdose is by a factor of", isum/(len(offenders)))
	print ("Number of offenders is", len(offendersGen))
	# Write out file
	with open('offenders.csv', 'w') as f:
		wr = csv.writer(f, quoting=csv.QUOTE_ALL)
		wr.writerow(offenders)
	return offendersGen

def writeResults(offendersGen):
	#Write powerflow results for generation and waterheater, zipload, and hvac (house) load objects
	#need to fix up testing for if file exsists based upon name written
	substation = pd.read_csv(('measured_substation_power.csv'), comment='#', names=['timestamp', 'measured_real_power'])
	substation_power = substation['measured_real_power'][0]
	ziploads =  pd.read_csv(('measured_load_ziploads.csv'), comment='#', names=['timestamp', 'measured_real_power'])
	zipload_power = ziploads['measured_real_power'][0]
	waterheaters = pd.read_csv(('measured_load_waterheaters.csv'), comment='#', names=['timestamp', 'measured_real_power'])
	waterheater_power = waterheaters['measured_real_power'][0]
	HVAC = pd.read_csv(('measured_HVAC.csv'), comment='#', names=['timestamp', 'heating_power', 'cooling_power'])
	HVAC_power = HVAC['heating_power'][0], HVAC['cooling_power'][0]
	if os.path.isfile('measured_wind_0'):
		wind = pd.read_csv(('measured_wind_0.csv'), comment='#', names=['timestamp', 'Pconv'])
		wind_power = wind['Pconv'][0]
	triplex_solar_use = pd.read_csv(('measured_load_triplex.csv'), comment='#', names=['timestamp', 'measured_real_power'])
	triplex_solar_use_power = triplex_solar_use['measured_real_power'][0]

	#Print Results
	print "Substation power", substation_power
	print "Zipload Power Use", zipload_power*1000
	print "Waterheater Power Use", waterheater_power*1000
	print "HVAC Power Use", (HVAC_power[0]+HVAC_power[1])*1000
	print "Triplex/Rooftop solar use", (triplex_solar_use_power)
	#convert results to watts, write to dataframe
	df=pd.DataFrame(columns=('result', 'value'))
	df.loc[0]=["Number of offenders", len(offendersGen)]
	df.loc[1]=["Substation Power", substation_power]
	df.loc[4]=["Zipload Power Use", zipload_power*1000]
	df.loc[5]=["Waterheater Power Use", waterheater_power*1000]
	df.loc[6]=["HVAC Power Use", (HVAC_power[0]+HVAC_power[1])*1000]
	df.loc[7]=["rooftop solar use", triplex_solar_use_power]
	if os.path.isfile('measured_wind_0'):
		#temporary test
		df.loc[7]=['wind power', wind_power]
	df.loc[8]=['current time', datetime.today()]
	#Write Dataframe to .csv
	df.to_csv('Results.csv')



def _debugging(filePath):
	# Location
	# modelLoc = pJoin(__neoMetaModel__._omfDir,"data","Model","admin","Automated Testing of " + modelName)
	# Blow away old test results if necessary.
	fileNames = ['measured_substation_power.csv', 'measured_solar_0.csv', 'measured_solar_1.csv', 'measured_load_ziploads.csv', 
					'measured_load_waterheaters.csv', 'measured_HVAC.csv', 'Results.csv']
	files = [f for f in os.listdir('.')]
	for f in files:
		if f in fileNames:
			os.remove(f) 
	#Begin Main Function
	name_volt_dict = ConvertAndwork(filePath)
	offendersGen = ListOffenders(name_volt_dict)
	writeResults(offendersGen)
	# Open Distnetviz on glm
	omf.distNetViz.viz('outGLMtest_rooftop.glm') #or model.omd

	# Remove Feeder
	os.remove('outGLMtest.glm')

	# Visualize Voltage Regulation
	# chart = drawPlot('outGLMtest.glm', neatoLayout=True, edgeCol="PercentOfRating", nodeCol="perUnitVoltage", nodeLabs="Value", edgeLabs="Name", customColormap=True, rezSqIn=225, gldBinary=omf.omfDir + '/solvers/gridlabd_gridballast/local_gd/bin/gridlabd')
	# chart.savefig('outGLM.png')
if __name__ == '__main__':
	try: 
		#Parse Command Line
		parser = argparse.ArgumentParser(description='Converts an OMD to GLM and runs it on gridlabd')
		parser.add_argument('file_path', metavar='base', type=str,
		                    help='Path to OMD. Put in quotes.')
		args = parser.parse_args()
		filePath = args.file_path
		_debugging(filePath)
	except:
		_debugging('/Users/tuomastalvitie/Desktop/gridballast_gld_simulations/Feeders/UCS_Egan_Housed_Solar_rooftop.omd')