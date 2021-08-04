#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
GeoNode Utilities:
-----------------

Reads from GeoNode servers and creates datasets.

"""
import logging
from collections import OrderedDict

from typing import List, Dict, Optional, Tuple, Union, Callable, Any, Type

from hdx.data.organization import Organization
from hdx.utilities import get_uuid
from hdx.utilities.dateparse import parse_date, default_date
from six.moves.urllib.parse import quote_plus

from hdx.data.dataset import Dataset
from hdx.data.resource import Resource
from hdx.data.showcase import Showcase
from hdx.location.country import Country
from hdx.utilities.downloader import Download
from hdx.utilities.loader import load_yaml
from hdx.utilities.path import script_dir_plus_file
from slugify import slugify

from hdx.scraper.geonode.version import get_geonode_version

logger = logging.getLogger(__name__)


def create_dataset_showcase(dataset, showcase, **kwargs):
    # type: (Dataset, Showcase, Any) -> None
    """
    Create dataset and showcase

    Args:
        dataset (Dataset): Dataset to create
        showcase (Showcase): Showcase to create
        **kwargs: Args to pass to dataset create_in_hdx call

    Returns:
        None

    """
    dataset.update_from_yaml()
    dataset.create_in_hdx(remove_additional_resources=True, hxl_update=False, **kwargs)
    showcase.create_in_hdx()
    showcase.add_dataset(dataset)


def delete_from_hdx(dataset):
    # type: (Dataset) -> None
    """
    Delete dataset and any associated showcases

    Args:
        dataset (Dataset): Dataset to delete

    Returns:
        None

    """
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
        self.geonode_urls = [geonode_url]
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
        # type: (bool) -> List[Dict]
        """
        Get countries from GeoNode

        Args:
            use_count (bool): Whether to use null count metadata to exclude countries. Defaults to True.

        Returns:
            List[Dict]: List of countries in form (iso3 code, name)

        """
        response = self.downloader.download('%s/api/regions' % self.geonode_urls[0])
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
        response = self.downloader.download('%s/api/layers%s' % (self.geonode_urls[0], regionstr))
        jsonresponse = response.json()
        return jsonresponse['objects']

    @staticmethod
    def get_orgname(metadata, orgclass=Organization):
        # type: (Dict, Type) -> str
        """
        Get orgname from Dict if available or use orgid from Dict to look up organisation name

        Args:
            metadata (Dict): Dictionary containing keys: maintainerid, orgid, updatefreq, subnational
            orgclass (Type): Class to use for look up. Defaults to Organization.

        Returns:
            str: Organisation name

        """
        orgname = metadata.get('orgname')
        if not orgname:
            organisation = orgclass.read_from_hdx(metadata['orgid'])
            orgname = organisation['name']
            metadata['orgname'] = orgname
        return orgname

    def generate_dataset_and_showcase(self, countryiso, layer, metadata, get_date_from_title=False, process_dataset_name=lambda x: x, dataset_tags_mapping=dict()):
        # type: (str, Dict, Dict, bool, Callable[[str], str], Dict[str, List]) -> Tuple[Optional[Dataset], Optional[List], Optional[Showcase]]
        """
        Generate dataset and showcase for GeoNode layer

        Args:
            countryiso (str): ISO 3 code of country
            layer (Dict): Data about layer from GeoNode
            metadata (Dict): Dictionary containing keys: maintainerid, orgid, updatefreq, subnational
            get_date_from_title (bool): Whether to remove dates from title. Defaults to False.
            process_dataset_name (Callable[[str], str]): Function to change the dataset name. Defaults to lambda x: x.
            dataset_tags_mapping (Dict[str, List]): Mapping from dataset name to additional tags. Defaults to empty dictionary.

        Returns:
            Tuple[Optional[Dataset],List,Optional[Showcase]]: Dataset, date ranges in dataset title and Showcase objects or None, None, None
        """
        origtitle = layer['title'].strip()
        notes = layer['abstract']
        abstract = notes.lower()
        for term in self.ignore_data:
            if term in abstract:
                logger.warning('Ignoring %s as term %s present in abstract!' % (origtitle, term))
                return None, None, None

        dataset = Dataset({'title': origtitle})
        if get_date_from_title:
            ranges = dataset.remove_dates_from_title(change_title=True, set_dataset_date=True)
        else:
            ranges = list()
        title = dataset['title']
        logger.info('Creating dataset: %s' % title)
        detail_url = layer['detail_url']
        supplemental_information = layer['supplemental_information']
        if supplemental_information.lower()[:7] == 'no info':
            dataset_notes = notes
        else:
            dataset_notes = '%s\n\n%s' % (notes, supplemental_information)
        dataset_date = parse_date(layer['date'])
        if origtitle == title:
            dataset.set_date_of_dataset(dataset_date)
        else:
            dataset_notes = '%s\n\nOriginal dataset title: %s' % (dataset_notes, origtitle)
            logger.info('Using %s-%s instead of %s for dataset date' % (ranges[0][0], ranges[0][1], dataset_date))
        slugified_name = slugify('%s_geonode_%s' % (self.get_orgname(metadata), title))
        slugified_name = process_dataset_name(slugified_name)
        slugified_name = slugified_name[:90]
        dataset['name'] = slugified_name
        dataset['notes'] = dataset_notes
        dataset.set_maintainer(metadata['maintainerid'])
        dataset.set_organization(metadata['orgid'])
        updatefreq = metadata.get('updatefreq', 'As needed')
        dataset.set_expected_update_frequency(updatefreq)
        subnational = metadata.get('subnational', True)
        dataset.set_subnational(subnational)
        dataset.add_country_location(countryiso)
        tags = dataset_tags_mapping.get(slugified_name, list())
        tags.append('geodata')
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
        if '%3Ageonode%3A' in detail_url:
            geonode_url = 'https://%s' % detail_url.rsplit('/', 1)[-1].split('%3Ageonode%3A')[0]
            if geonode_url not in self.geonode_urls:
                self.geonode_urls.append(geonode_url)
        else:
            geonode_url = self.geonode_urls[0]
        typename = 'geonode:%s' % detail_url.rsplit('geonode%3A', 1)[-1]
        resource = Resource({
            'name': '%s shapefile' % title,
            'url': '%s/geoserver/wfs?format_options=charset:UTF-8&typename=%s&outputFormat=SHAPE-ZIP&version=1.0.0&service=WFS&request=GetFeature' % (geonode_url, typename),
            'description': 'Zipped Shapefile. %s' % notes
        })
        resource.set_file_type('zipped shapefile')
        dataset.add_update_resource(resource)
        resource = Resource({
            'name': '%s geojson' % title,
            'url': '%s/geoserver/wfs?srsName=%s&typename=%s&outputFormat=json&version=1.0.0&service=WFS&request=GetFeature' % (geonode_url, srid, typename),
            'description': 'GeoJSON file. %s' % notes
        })
        resource.set_file_type('GeoJSON')
        dataset.add_update_resource(resource)

        showcase = Showcase({
            'name': '%s-showcase' % slugified_name,
            'title': title,
            'notes': notes,
            'url': '%s%s' % (self.geonode_urls[0], detail_url),
            'image_url': layer['thumbnail_url']
        })
        showcase.add_tags(tags)
        return dataset, ranges, showcase

    def generate_datasets_and_showcases(self, metadata, create_dataset_showcase=create_dataset_showcase,
                                        countrydata=None, get_date_from_title=False, process_dataset_name=lambda x: x,
                                        dataset_tags_mapping=dict(), **kwargs):
        # type: (Dict, Callable[[Dataset, Showcase, Any], None], Dict[str, Optional[str]], bool, Callable[[str], str], Dict[str, List], Any) -> List[str]
        """
        Generate datasets and showcases for all GeoNode layers

        Args:
            metadata (Dict): Dictionary containing keys: maintainerid, orgid, updatefreq, subnational
            create_dataset_showcase (Callable[[Dataset, Showcase, Any], None]): Function to call to create dataset and showcase
            countrydata (Dict[str, Optional[str]]): Dictionary of countrydata. Defaults to None (read from GeoNode).
            get_date_from_title (bool): Whether to remove dates from title. Defaults to False.
            process_dataset_name (Callable[[str], str]): Function to change the dataset name. Defaults to lambda x: x.
            dataset_tags_mapping (Dict[str, List]): Mapping from dataset name to additional tags. Defaults to empty dictionary.
            **kwargs: Args to pass to dataset create_in_hdx call

        Returns:
            List[str]: List of names of datasets added or updated

        """
        logger.info('--------------------------------------------------')
        logger.info('> Using HDX Python GeoNode Library %s' % get_geonode_version())
        if countrydata:
            countries = [countrydata]
        else:
            countries = self.get_countries()
            logger.info('Number of countries: %d' % len(countries))
        dataset_dates = OrderedDict()
        if 'batch' not in kwargs:
            kwargs['batch'] = get_uuid()
        for countrydata in countries:
            layers = self.get_layers(countrydata['layers'])
            logger.info('Number of datasets to upload in %s: %d' % (countrydata['name'], len(layers)))
            for layer in layers:
                dataset, ranges, showcase = self.generate_dataset_and_showcase(countrydata['iso3'], layer, metadata,
                                                                               get_date_from_title, process_dataset_name,
                                                                               dataset_tags_mapping=dataset_tags_mapping)
                if dataset:
                    dataset_name = dataset['name']
                    max_date = default_date
                    for range in ranges:
                        if range[1] > max_date:
                            max_date = range[1]
                    prev_max = dataset_dates.get(dataset_name)
                    if prev_max and prev_max > max_date:
                        logger.warning('Ignoring %s with max date %s!'
                                       ' %s (dates removed) with max date %s has been created already!' %
                                       (layer['title'], max_date, dataset_name, prev_max))
                        continue
                    create_dataset_showcase(dataset, showcase, **kwargs)
                    dataset_dates[dataset_name] = max_date
        return list(dataset_dates.keys())

    def delete_other_datasets(self, datasets_to_keep, metadata, delete_from_hdx=delete_from_hdx):
        # type: (List[str], Dict, Callable[[Dataset], None]) -> None
        """
        Delete all GeoNode datasets and associated showcases in HDX where layers have been deleted from
        the GeoNode server.

        Args:
            datasets_to_keep (List[str]): List of dataset names that are to be kept (they were added or updated)
            metadata (Dict): Dictionary containing keys: maintainerid, orgid, updatefreq, subnational
            delete_from_hdx (Callable[[Dataset], None]): Function to call to delete dataset

        Returns:
            None

        """
        for dataset in Dataset.search_in_hdx(fq='organization:%s' % self.get_orgname(metadata)):
            if dataset['maintainer'] != metadata['maintainerid']:
                continue
            if dataset['name'] in datasets_to_keep:
                continue
            if not any(x in dataset.get_resource()['url'] for x in self.geonode_urls):
                continue
            logger.info('Deleting %s' % dataset['title'])
            delete_from_hdx(dataset)
