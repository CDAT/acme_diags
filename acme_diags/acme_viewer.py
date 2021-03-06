import os
import sys
import glob
import urllib2
import fnmatch
import datetime
import shutil
import collections
from bs4 import BeautifulSoup
import acme_diags
from cdp.cdp_viewer import OutputViewer
from acme_diags.driver.utils import get_output_dir, get_set_name

# Dict of 
# {
#   set_num: {
#       case_id: {
#           row_name: {
#               season: filename
#           }
#       }
#   }
# }
# Order is page(set_num) -> group(case_id) -> row(row_name) -> col(season) -> filename
# Used when actually inserting the cols into the viewer
# needed so we can have a cols in order of ANN, DJF, MAM, JJA, SON
ROW_INFO = collections.OrderedDict()

def _copy_acme_logo(root_dir):
    """Copy over ACME_Logo.png to root_dir/viewer"""
    src_pth = os.path.join(sys.prefix, "share", "acme_diags", "ACME_Logo.png")
    dst_path = os.path.join(root_dir, "viewer")
    shutil.copy(src_pth, dst_path)

def _get_acme_logo_path(root_dir, html_path):
    """Based of the root dir of the viewer and the current 
    dir of the html, get the relative path of the ACME logo"""
    # when current_dir = myresults-07-11/viewer/index.html, the image is in myresults-07-11/viewer/viewer/ACME_Logo.png
    # so there's no need to move some number of directories up.
    # That's why we have - 3
    relative_dir = html_path.replace(root_dir + '/', '')
    dirs_to_go_up = len(relative_dir.split('/')) - 1
    pth = os.path.join('.')
    for _ in range(0, dirs_to_go_up):
        pth = os.path.join(pth, '..')
    pth = os.path.join(pth, 'viewer', 'ACME_Logo.png')
    return pth

def _add_header(path, version, model_name, time, logo_path):
    """Add the header to the html located at path"""

    # We're inserting the following in the body under navbar navbar-default
    # <div id="acme-header" style="background-color:#dbe6c5; float:left; width:45%">
	# 	<p style="margin-left:5em">
	# 		<b>ACME Diagnostics Package [VERSION]</b><br>
	# 		Test model name: [SOMETHING]<br>
	# 		Date created: [DATE]<br>
	# 	</p>
	# </div>
	# <div id="acme-header2" style="background-color:#dbe6c5; float:right; width:55%">
	# 	<img src="ACME_logo.png" alt="logo" style="width:161px; height:70px; background-color:#dbe6c5">
	# </div>
    
    soup = BeautifulSoup(open(path), "html5lib")
    old_header = soup.find_all("nav", "navbar navbar-default")
    if len(old_header) is not 0:
        old_header[0].decompose()

    header_div = soup.new_tag("div", id="acme-header", style="background-color:#dbe6c5; float:left; width:45%")
    p = soup.new_tag("p", style="margin-left:5em")

    bolded_title = soup.new_tag("b")
    bolded_title.append("ACME Diagnostics Package {}".format(version))
    bolded_title.append(soup.new_tag("br"))
    p.append(bolded_title)

    p.append("Model: {}".format(model_name))
    p.append(soup.new_tag("br"))

    p.append("Created {}".format(time))

    header_div.append(p)
    soup.body.insert(0, header_div)

    img_div = soup.new_tag("div", id="acme-header2", style="background-color:#dbe6c5; float:right; width:55%")
    img = soup.new_tag("img", src=logo_path, alt="logo", style="width:161px; height:71px; background-color:#dbe6c5")
    img_div.append(img)
    soup.body.insert(1, img_div)

    html = soup.prettify("utf-8")
    with open(path, "wb") as f:
        f.write(html)

def h1_to_h3(path):
    """Change any <h1> to <h3> because h1 is just too big"""
    soup = BeautifulSoup(open(path), "html5lib")
    h1 = soup.find('h1')
    if h1 is None:
        return
    h1.name = 'h3'

    html = soup.prettify("utf-8")
    with open(path, "wb") as f:
        f.write(html)


def _extras(root_dir, parameters):
    """Add extras (header, etc) to the generated htmls"""
    _copy_acme_logo(root_dir)

    index_files = []
    for root, dirnames, filenames in os.walk(root_dir):
        for filename in fnmatch.filter(filenames, 'index.html'):
            pth = os.path.join(root, filename)
            index_files.append(pth)
    dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    img_path = os.path.join('viewer', 'ACME_Logo.png')

    for f in index_files:
        path = _get_acme_logo_path(root_dir, f)
        _add_header(f, acme_diags.__version__, parameters[0].test_name, dt, path)
        h1_to_h3(f)

def _add_pages_and_top_row(viewer, parameters):
    """Add the page and columns of the page"""
    set_to_seasons = collections.OrderedDict()  # dict of {set: [seasons]}
    for p in parameters:
        for set_num in p.sets:
            set_num = get_set_name(set_num)
            for ssn in p.seasons:
                if set_num not in set_to_seasons:
                    set_to_seasons[set_num] = []
                set_to_seasons[set_num].append(ssn)

    for set_num, seasons in set_to_seasons.iteritems():
        ROW_INFO[set_num] = collections.OrderedDict()
        col_labels = ['Description']
        for s in ['ANN', 'DJF', 'MAM', 'JJA', 'SON']:
            if s in seasons:
                col_labels.append(s)
        viewer.add_page("{}".format(_better_page_name(set_num)), col_labels)

def _get_description(var, parameters):
    """Get the description for the variable from the parameters"""
    if hasattr(parameters, 'viewer_descr') and var in parameters.viewer_descr:
        return parameters.viewer_descr[var]
    return var

def _better_page_name(old_name):
    """Use a longer, more descriptive name for the pages."""
    if old_name == 'zonal_mean_xy':
        return 'Zonal mean line plots'
    elif old_name == 'zonal_mean_2d':
        return 'Pressure-Latitude zonal mean contour plots'
    elif old_name == 'lat_lon':
        return 'Latitude-Longitude contour maps'
    elif old_name == 'polar':
        return 'Polar contour maps'
    elif old_name == 'cosp_histogram':
        return 'CloudTopHeight-Tau joint histograms'
    else:
        return old_name

def create_viewer(root_dir, parameters, ext):
    """Based of the parameters, find the files with
    extension ext and create the viewer in root_dir."""

    viewer = OutputViewer(path=root_dir, index_name='ACME Diagnostics')
    _add_pages_and_top_row(viewer, parameters)

    for parameter in parameters:
        for set_num in parameter.sets:
            set_num = get_set_name(set_num)

            # Add all of the files with extension ext from the case_id/ folder'
            pth = get_output_dir(set_num, parameter)  # ex: myresults/lat_lon

            # Filenames are like:
            # ref_name-variable-season-region
            # or
            # ref_name-variable-plev'mb'-season-region
            ref_name = parameter.ref_name
            for var in parameter.variables:
                for season in parameter.seasons:
                    for region in parameter.regions:
                        row_name_and_fnm = []  # because some parameters have plevs, there might be more than one row_name, fnm pair


                        if parameter.plevs == []:  # 2d variables
                            row_name = '{} {}'.format(var, region)
                            fnm = '{}-{}-{}-{}'.format(ref_name, var, season, region)
                            row_name_and_fnm.append((row_name, fnm))
                        else:  # 3d variables
                            for plev in parameter.plevs:
                                row_name = '{} {} {}'.format(var, str(int(plev)) + ' mb', region)
                                fnm = '{}-{}-{}-{}-{}'.format(ref_name, var, int(plev), season, region)
                                row_name_and_fnm.append((row_name, fnm))

                        for row_name, fnm in row_name_and_fnm:
                            if parameter.case_id not in ROW_INFO[set_num]:
                                ROW_INFO[set_num][parameter.case_id] = collections.OrderedDict()
                            if row_name not in ROW_INFO[set_num][parameter.case_id]:
                                ROW_INFO[set_num][parameter.case_id][row_name] = collections.OrderedDict()
                                ROW_INFO[set_num][parameter.case_id][row_name]['descr'] = _get_description(var, parameter)
                            # format fnm to support relative paths
                            ROW_INFO[set_num][parameter.case_id][row_name][season] = os.path.join('..', '{}'.format(set_num), parameter.case_id, fnm)

    # add all of the files in from the case_id/ folder in ANN, DJF, MAM, JJA, SON order
    for set_num in ROW_INFO:
        viewer.set_page("{}".format(_better_page_name(set_num)))

        for group in ROW_INFO[set_num]:
            try:             
                viewer.set_group(group)
            except RuntimeError:
                viewer.add_group(group)

            for row_name in ROW_INFO[set_num][group]:
                try:
                     viewer.set_row(row_name)
                except RuntimeError:
                     # row of row_name wasn't in the viewer, so add it
                     viewer.add_row(row_name)
                     viewer.add_col(ROW_INFO[set_num][group][row_name]['descr'])  # the description, currently the var

                for col_season in viewer.page.columns[1:]:  # [1:] is to ignore 'Description' col 
                    fnm = ROW_INFO[set_num][group][row_name][col_season]
                    formatted_files = []
                    if parameters[0].save_netcdf:
                        nc_files = [fnm + nc_ext for nc_ext in ['_test.nc', '_ref.nc', '_diff.nc']]
                        formatted_files = [{'url': f, 'title': f} for f in nc_files]
                    viewer.add_col(fnm + '.' + ext, is_file=True, title=col_season, other_files=formatted_files)

    viewer.generate_viewer(prompt_user=False)
    _extras(root_dir, parameters)

