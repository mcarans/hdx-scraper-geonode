[![Build Status](https://travis-ci.org/OCHA-DAP/hdx-scraper-geonode.svg?branch=master&ts=1)](https://travis-ci.org/OCHA-DAP/hdx-scraper-geonode) [![Coverage Status](https://coveralls.io/repos/github/OCHA-DAP/hdx-scraper-geonode/badge.svg?branch=master&ts=1)](https://coveralls.io/github/OCHA-DAP/hdx-scraper-geonode?branch=master)

The HDX Scraper Geonode Library enables easy building of scrapers for extracting data 
from geonode servers. 

## Usage

The library has detailed API documentation which can be found
here: <http://ocha-dap.github.io/hdx-scraper-geonode/>. The code for the
library is here: <https://github.com/ocha-dap/hdx-scraper-geonode>.

## GeoNodeToHDX Class

You should create an object of the GeoNodeToHDX class:
 
    geonodetohdx = GeoNodeToHDX('https://geonode.wfp.org', downloader)
    geonodetohdx = GeoNodeToHDX('https://geonode.themimu.info', downloader)

It has high level methods generate_datasets_and_showcases and 
delete_other_datasets:

    # generate datasets and showcases reading country and layer information from the GeoNode
    datasets = generate_datasets_and_showcases('maintainerid', 'orgid', 'orgname', updatefreq='Adhoc', 
                                               subnational=True)
    # generate datasets and showcases reading layer information ignoring region (country) in layers call
    countrydata = {'iso3': 'MMR', 'name': 'Myanmar', 'layers': None}
    datasets = generate_datasets_and_showcases('maintainerid', 'orgid', 'orgname', updatefreq='Adhoc', 
                                               subnational=True, countrydata=countrydata)
    # delete any datasets and associated showcases from HDX that are not in the list datasets
    # (assuming matching organisation id, maintainer id and geonode url in the resource url)
    delete_other_datasets(datasets)

If you need more fine grained control, it has low level methods
get_locationsdata, get_layersdata, generate_dataset_and_showcase:

    # get countries where count > 0
    countries = geonodetohdx.get_countries(use_count=True)
    # get layers for country with ISO 3 code SDN
    layers = geonodetohdx.get_layers(countryiso='SDN')
    # get layers for all countries
    layers = get_layers(countryiso=None)

There are default terms to be ignored and mapped. These can be overridden by
creating a YAML configuration with the new configuration in this format:

    ignore_data:
      - deprecated

    category_mapping:
      Elevation: 'elevation - topography - altitude'
      'Inland Waters': river

    titleabstract_mapping:
      bridges:
        - bridges
        - transportation
        - 'facilities and infrastructure'
      idp:
        camp:
          - 'displaced persons locations - camps - shelters'
          - 'internally displaced persons - idp'
        else:
          - 'internally displaced persons - idp'
  
ignore_data are any terms in the abstract that mean that the dataset 
should not be added to HDX.
  
category_mapping are mappings from the category field category__gn_description 
to HDX metadata tags.
  
titleabstract_mapping are mappings from terms in the title or abstract to 
HDX metadata tags.

For more fine grained tuning of these, you retrieve the dictionaries and
manipulate them directly:

    geonodetohdx = GeoNodeToHDX('https://geonode.wfp.org', downloader)
    ignore_data = geonodetohdx.get_ignore_data() 
    category_mapping = geonodetohdx.get_category_mapping() 
    titleabstract_mapping = geonodetohdx.get_titleabstract_mapping()         