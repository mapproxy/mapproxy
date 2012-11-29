#
# spec file for package MapProxy (1.4.0)
#
# Copyright (c) 2012 Angelos Tzotsos <tzotsos@opensuse.org>
#
# This file and all modifications and additions to the MapProxy
# package are under the same license as the package itself.

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

%define pyname mapproxy
%define filename MapProxy

Name:           python-%{pyname}
Version:        1.4.0
Release:        0
Summary:        MapProxy is an open source proxy for geospatial data
License:        MIT
Url:            http://mapproxy.org/
Group:          Productivity/Scientific/Other
Source0:        %{filename}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-build
BuildArch:      noarch
BuildRequires:  python-devel 
BuildRequires:  python-setuptools
BuildRequires:  python-imaging
BuildRequires:	python-yaml
BuildRequires:	libproj0
BuildRequires:	libgeos0
BuildRequires:	python-gdal
BuildRequires:  fdupes
Requires:	python
Requires:	python-Shapely
Requires:	python-lxml
Requires:	python-imaging
Requires:	python-yaml
Requires:	libproj0
Requires:	libgeos0
Requires:	python-gdal

%description
MapProxy is an open source proxy for geospatial data. It caches, accelerates and transforms data from existing map services and serves any desktop or web GIS client.

%prep
%setup -q -n %{filename}-%{version}

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}

python setup.py install --prefix=%{_prefix} --root=%{buildroot} \
                                            --record-rpm=INSTALLED_FILES

%fdupes -s %{buildroot}

%clean
rm -rf %{buildroot}

%files -f INSTALLED_FILES
%defattr(-,root,root,-)

%changelog
