import platform, os, sys, urllib, subprocess

source_dir = os.path.dirname(__file__)

# Check that we're only using python3
if sys.version_info[0] != 3:
	print(f'You are using python version {sys.version}')
	print('We only support python major version 3. Install aborted.')
	sys.exit()

# Detect platform
major_platform = platform.system()
linux_distro = str(subprocess.check_output(['cat','/etc/os-release'])).lower()

if major_platform == "Linux" and "ubuntu" in linux_distro:
	os.system("sudo ACCEPT_EULA=Y apt-get -yq install mssql-tools msodbcsql mdbtools") # workaround for the package EULA, which otherwise breaks upgrade!!
	os.system("sudo apt-get -y update")# && sudo apt-get -y upgrade") # Make sure apt-get is updated to prevent any weird package installation issues
	os.system("sudo apt-get -y install language-pack-en") # Install English locale 
	os.system("sudo DEBIAN_FRONTEND=noninteractive apt-get -y install git python3-pip python3-dev python3-numpy unixodbc-dev libfreetype6-dev pkg-config alien python3-pydot python3-tk libblas-dev liblapack-dev libatlas-base-dev gfortran splat")
	os.system("sudo apt-get -y install ffmpeg python3-cairocffi") # Separate from above to better support debian.
	os.system("sudo alien -i omf/static/gridlabd-4.0.0-1.el6.x86_64.rpm")
	os.system("sudo apt-get install -f")
	os.system(f"{sys.executable} -m pip install --upgrade pip setuptools")
	os.system(f"{sys.executable} -m pip install -r requirements.txt")
	os.system(f"{sys.executable} setup.py develop")
elif major_platform == "Linux" and "ubuntu" not in linux_distro:
	# CentOS and or Redhat install
	os.system("sudo yum -y update") # Make sure yum is updated to prevent any weird package installation issues
	os.system("sudo yum -y install git gcc xerces-c python-devel tkinter")
	os.system("sudo yum --enablerepo=extras install epel-release")
	os.system("sudo yum -y install mdbtools")
	os.system("sudo rpm --import http://li.nux.ro/download/nux/RPM-GPG-KEY-nux.ro")
	os.system("sudo rpm -Uvh http://li.nux.ro/download/nux/dextop/el7/x86_64/nux-dextop-release-0-1.el7.nux.noarch.rpm")
	os.system("sudo yum -y install ffmpeg ffmpeg-devel -y")
	os.system("sudo yum -y install python-pip")
	os.system("sudo rpm -Uvh omf/static/gridlabd-4.0.0-1.el6.x86_64.rpm")
	os.system(f"{sys.executable} -m pip install --upgrade pip")
	os.system(f"{sys.executable} -m pip install -r requirements.txt")
	os.system(f"{sys.executable} -m pip install --ignore-installed six")
	os.system(f"{sys.executable} setup.py develop")
elif major_platform == 'Windows':
	os.system("choco install -y --no-progress ffmpeg")
	os.system("choco install -y --no-progress pip")
	# TODO: find way to install mdbtools.
	os.system(".\\omf\\static\\gridlabd-4.0_RC1.exe /silent")
	#TODO: install SPLAT
	os.system(f"{sys.executable} -m pip install --upgrade pip")
	os.system(f"{sys.executable} -m pip install -r requirements.txt")
	os.system(f"{sys.executable} setup.py develop")
elif major_platform == "Darwin": # MacOS
	os.system("HOMEBREW_NO_AUTO_UPDATE=1 brew wget install ffmpeg git mdbtools") # Set no-update to keep homebrew from blowing away python3.
	os.system("sudo hdiutil attach omf/static/gridlabd-4.0_RC1.dmg")
	os.system('sudo installer -package "/Volumes/GridLAB-D 4.0.0/gridlabd.mpkg" -target /')
	os.system('sudo hdiutil detach "/Volumes/GridLAB-D 4.0.0"')
	os.system("wget https://www.qsl.net/kd2bd/splat-1.4.2-osx.tgz")
	os.system("sudo tar -xvzf splat-1.4.2-osx.tgz")
	os.system('''
		cd splat-1.4.2;
		sed -i '' 's/ans=""/ans="2"/g' configure;
		sudo bash configure;
	''') # sed is to hack the build to work without user input.
	os.system(f"{sys.executable} -m pip install -r requirements.txt")
	os.system(f"{sys.executable} setup.py develop")
else:
	print("Your operating system is not currently supported. Platform detected: " + str(platform.system()) + str(platform.linux_distribution()))
