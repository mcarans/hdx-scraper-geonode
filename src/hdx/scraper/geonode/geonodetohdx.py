#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
GeoNode Utilities:
-----------------

Reads from GeoNode servers and creates datasets.

"""
from datetime import datetime
import logging
from typing import List, Dict, Optional, Tuple, Union, Callable
from six.moves.urllib.parse import quote_plus, unquote_plus

from hdx.data.dataset import Dataset
from hdx.data.resource import Resource
from hdx.data.showcase import Showcase
from hdx.location.country import Country
from hdx.utilities.downloader import Download
from hdx.utilities.loader import load_yaml
from hdx.utilities.path import script_dir_plus_file
from slugify import slugify

logger = logging.getLogger(__name__)


def create_dataset_showcase(dataset, showcase):
    dataset.update_from_yaml()
    dataset.create_in_hdx(remove_additional_resources=True, hxl_update=False)
    showcase.create_in_hdx()
    showcase.add_dataset(dataset)


def delete_from_hdx(dataset):
    logger.info('Deleting %s and any associated showcases' % dataset['title'])
    for showcase in dataset.get_showcases():
        showcase.delete_from_hdx()
    dataset.delete_from_hdx()


class GeoNodeToHDX(object):
    """
    Utilities to bring GeoNode data into HDX. hdx_geonode_config_yaml points to a YAML file
    that overrides base values and is in this format:

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

    Args:
        geonode_url (str): GeoNode server url
        downloader (Download): Download object from HDX Python Utilities
        hdx_geonode_config_yaml (Optional[str]): Configuration file for scraper
    """

    def __init__(self, geonode_url, downloader, hdx_geonode_config_yaml=None):
        # type: (str, Download, Optional[str]) -> None
        self.geonode_url = geonode_url
        self.downloader = downloader
        base_hdx_geonode_config_yaml = script_dir_plus_file('hdx_geonode.yml', GeoNodeToHDX)
        geonode_config = load_yaml(base_hdx_geonode_config_yaml)
        if hdx_geonode_config_yaml is not None:
            geonode_config.update(load_yaml(hdx_geonode_config_yaml))
        self.ignore_data = geonode_config['ignore_data']
        self.category_mapping = geonode_config['category_mapping']
        self.titleabstract_mapping = geonode_config['titleabstract_mapping']

    def get_ignore_data(self):
        # type: () -> List[str]
        """
        Get terms in the abstract that mean that the dataset should not be added to HDX

        Returns:
            List[str]: List of terms in the abstract that mean that the dataset should not be added to HDX

        """
        return self.ignore_data

    def get_category_mapping(self):
        # type: () -> Dict[str,str]
        """
        Get mappings from the category field category__gn_description to HDX metadata tags

        Returns:
            Dict[str,str]: List of mappings from the category field category__gn_description to HDX metadata tags

        """
        return self.category_mapping

    def get_titleabstract_mapping(self):
        # type: () -> Dict[str,Union[Dict,List]]
        """
        Get mappings from terms in the title or abstract to HDX metadata tags

        Returns:
            Dict[str,Union[Dict,List]]: List of mappings from terms in the title or abstract to HDX metadata tags

        """
        return self.titleabstract_mapping

    def get_countries(self, use_count=True):
        # type: (bool) -> List[Tuple]
        """
        Get countries from GeoNode

        Args:
            use_count (bool): Whether to use null count metadata to exclude countries. Defaults to True.

        Returns:
            List[Tuple]: List of countries in form (iso3 code, name)

        """
        response = self.downloader.download('%s/api/regions' % self.geonode_url)
        jsonresponse = response.json()
        countries = list()
        for location in jsonresponse['objects']:
            loccode = location['code']
            locname = location['name_en']
            if use_count:
                count = location.get('count')
                if count is None:
                    logger.info('Location %s (%s) has nonexistent or null count!' % (locname, loccode))
                    continue
                if not count:
                    logger.info('Location %s (%s) has empty or zero count!' % (locname, loccode))
                    continue
            countryname = Country.get_country_name_from_iso3(loccode)
            if countryname is None:
                logger.info("Location %s (%s) isn't a country!" % (locname, loccode))
                continue
            countries.append({'iso3': loccode, 'name': countryname, 'layers': loccode})
        return countries

    def get_layers(self, countryiso=None):
        # type: (Optional[str]) -> List[Dict]
        """
        Get layers from GeoNode optionally for a particular country

        Args:
            countryiso (Optional[str]): ISO 3 code of country from which to get layers. Defaults to None (all countries).

        Returns:
            List[Dict]: List of layers

        """
        if countryiso is None:
            regionstr = ''
        else:
            regionstr = '/?regions__code__in=%s' % countryiso
        response = self.downloader.download('%s/api/layers%s' % (self.geonode_url, regionstr))
        jsonresponse = response.json()
        return jsonresponse['objects']

    def generate_dataset_and_showcase(self, countryiso, layer, maintainerid, orgid, orgname, updatefreq='Adhoc',
                                      subnational=True):
        # type: (str, Dict, str, str, str, str, bool) -> Tuple[Optional[Dataset],Optional[Showcase]]
        """
        Generate dataset and showcase for GeoNode layer

        Args:
            countryiso (str): ISO 3 code of country
            layer (Dict): Data about layer from GeoNode
            maintainerid (str): Maintainer ID
            orgid (str): Organisation ID
            orgname (str): Organisation name
            updatefreq (str): Update frequency. Defaults to Adhoc.
            subnational (bool): Subnational. Default to True.

        Returns:
            Tuple[Optional[Dataset],Optional[Showcase]]: Dataset and Showcase objects or None, None

        """
        title = layer['title']
        notes = layer['abstract']
        abstract = notes.lower()
        for term in self.ignore_data:
            if term in abstract:
                logger.warning('Ignoring %s as term %s present in abstract!' % (title, term))
                return None, None
        logger.info('Creating dataset: %s' % title)
        typename = layer['detail_url'].rsplit('/', 1)[-1]
        slugified_name = slugify(unquote_plus('%s_%s' % (orgname, typename)))
        try:
            datetime.strptime(slugified_name[-8:], '%Y%m%d')
            if slugified_name[-9] == '-':
                slugified_name = slugified_name[:-9]
        except ValueError:
            pass
        supplemental_information = layer['supplemental_information']
        if supplemental_information.lower()[:7] == 'no info':
            dataset_notes = notes
        else:
            dataset_notes = '%s\n\n%s' % (notes, supplemental_information)
        dataset = Dataset({
            'name': slugified_name,
            'title': title,
            'notes': dataset_notes
        })
        dataset.set_maintainer(maintainerid)
        dataset.set_organization(orgid)
        dataset.set_dataset_date(layer['date'])
        dataset.set_expected_update_frequency(updatefreq)
        dataset.set_subnational(subnational)
        dataset.add_country_location(countryiso)
        tags = ['geodata']
        tag = layer['category__gn_description']
        if tag is not None:
            if tag in self.category_mapping:
                tag = self.category_mapping[tag]
            tags.append(tag)
        title_abstract = ('%s %s' % (title, notes)).lower()
        for key in self.titleabstract_mapping:
            if key in title_abstract:
                mapping = self.titleabstract_mapping[key]
                if isinstance(mapping, list):
                    tags.extend(mapping)
                elif isinstance(mapping, dict):
                    found = False
                    for subkey in mapping:
                        if subkey == 'else':
                            continue
                        if subkey in title_abstract:
                            tags.extend(mapping[subkey])
                            found = True
                    if not found and 'else' in mapping:
                        tags.extend(mapping['else'])
        dataset.add_tags(tags)
        srid = quote_plus(layer['srid'])
        resource = Resource({
            'name': '%s shapefile' % title,
            'url': '%s/geoserver/wfs?format_options=charset:UTF-8&typename=%s&outputFormat=SHAPE-ZIP&version=1.0.0&service=WFS&request=GetFeature' % (self.geonode_url, typename),
            'description': 'Zipped Shapefile. %s' % notes
        })
        resource.set_file_type('zipped shapefile')
        dataset.add_update_resource(resource)
        resource = Resource({
            'name': '%s geojson' % title,
            'url': '%s/geoserver/wfs?srsName=%s&typename=%s&outputFormat=json&version=1.0.0&service=WFS&request=GetFeature' % (self.geonode_url, srid, typename),
            'description': 'GeoJSON file. %s' % notes
        })
        resource.set_file_type('GeoJSON')
        dataset.add_update_resource(resource)

        showcase = Showcase({
            'name': '%s-showcase' % slugified_name,
            'title': title,
            'notes': notes,
            'url': '%s%s' % (self.geonode_url, layer['detail_url']),
            'image_url': layer['thumbnail_url']
        })
        showcase.add_tags(tags)
        return dataset, showcase

    def generate_datasets_and_showcases(self, maintainerid, orgid, orgname, updatefreq='Adhoc', subnational=True,
                                        create_dataset_showcase=create_dataset_showcase, countrydata=None):
        # type: (str, str, str, str, bool, Callable[[Dataset, Showcase], None], Dict[str,Optional[str]]) -> List[Dataset]
        """
        Generate datasets and showcases for all GeoNode layers

        Args:
            maintainerid (str): Maintainer ID
            orgid (str): Organisation ID
            orgname (str): Organisation name
            updatefreq (str): Update frequency. Defaults to Adhoc.
            subnational (bool): Subnational. Default to True.
            create_dataset_showcase (Callable[[Dataset, Showcase], None]): Function to call to create dataset and showcase
            countrydata (Dict[str,Optional[str]]): Dictionary of countrydata. Defaults to None (read from GeoNode).

        Returns:
            List[Dataset]: List of datasets added or updated

        """
        if countrydata:
            countries = [countrydata]
        else:
            countries = self.get_countries()
            logger.info('Number of countries: %d' % len(countries))
        datasets = list()
        for countrydata in countries:
            layers = self.get_layers(countrydata['layers'])
            logger.info('Number of datasets to upload in %s: %d' % (countrydata['name'], len(layers)))
            for layer in layers:
                dataset, showcase = self.generate_dataset_and_showcase(countrydata['iso3'], layer, maintainerid, orgid,
                                                                       orgname, updatefreq, subnational)
                if dataset:
                    create_dataset_showcase(dataset, showcase)
                    datasets.append(dataset)
        return datasets

    def delete_other_datasets(self, datasets_to_keep, delete_from_hdx=delete_from_hdx):
        # type: (List[Dataset], Callable[[Dataset], None]) -> None
        """
        Delete all GeoNode datasets and associated showcases in HDX where layers have been deleted from
        the GeoNode server.

        Args:
            datasets_to_keep (List[Dataset]): List of datasets that are to be kept (they were added or updated)
            delete_from_hdx (Callable[[Dataset], None]): Function to call to delete dataset

        Returns:
            None

        """
        first_dataset = datasets_to_keep[0]
        dataset_names = [dataset['name'] for dataset in datasets_to_keep]
        for dataset in Dataset.search_in_hdx(fq='organization:%s' % first_dataset['organization']['name']):
            if dataset['maintainer'] != first_dataset['maintainer']:
                continue
            if dataset['name'] in dataset_names:
                continue
            if self.geonode_url not in dataset.get_resource()['url']:
                continue
            logger.info('Deleting %s' % dataset['title'])
            delete_from_hdx(dataset)
