#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
GeoNode Utilities:
-----------------

Reads from GeoNode servers and creates datasets.

"""
import re
from datetime import datetime
import logging
from typing import List, Dict, Optional, Tuple, Union, Callable

from hdx.utilities.dateparse import parse_date_range, parse_date
from hdx.utilities.text import remove_from_end
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
    YEAR_RANGE_PATTERN = re.compile('(\d\d\d\d)-(\d\d\d\d)')
    YEAR_TWICE_PATTERN = re.compile('(\d\d\d\d).{4,}(\d\d\d\d)')
    BETWEEN_BRACKETS_PATTERN = re.compile('[\(\[](.*)[\)\]]')

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
    def remove(string, toremove):
        # type: (str, str) -> str
        """
        Remove string from another string and delete any preceding comma

        Args:
            string (str): String to process
            toremove (str): String to remove

        Returns:
            str: String with other string removed

        """
        index = string.find(toremove)
        newstring = string[:index].strip()
        if newstring[-1] == ',':
            newstring = newstring[:-1]
        return ('%s%s' % (newstring, string[index + len(toremove):])).strip()


    @staticmethod
    def fuzzy_match(string):
        # type: (str) -> Tuple[str,Optional[datetime],Optional[datetime]]
        """
        Fuzzy match date in string, returning string minus the date and start and end dates

        Args:
            string (str): String to parse

        Returns:
            Tuple[str,Optional[datetime],Optional[datetime]]: Cleaned string, start and end dates

        """
        startdate = None
        enddate = None
        retstring = None
        try:
            fuzzy = dict()
            startdate, enddate = parse_date_range(string, fuzzy=fuzzy)
            restofstring = fuzzy['nondate']
            if restofstring:
                retstring = restofstring[0]
                if retstring[-1] == ',':
                    retstring = retstring[:-1]
                if len(retstring) > 1 and retstring[-1] == ' ' and retstring[-2] == ',':
                    retstring = '%s ' % retstring[:-2]
                if len(restofstring) > 1:
                    endstring = ''.join(restofstring[1:])
                    retstring = '%s%s' % (retstring, endstring)
                retstring = retstring.strip().replace('  ', ' ')
        except ValueError:
            pass
        return retstring, startdate, enddate

    @classmethod
    def get_date_from_title(cls, title, get_date_from_title=False):
        # type: (str, bool) -> Tuple[str,Optional[datetime],Optional[datetime]]
        """
        Get dataset date from title and clean title of dates

        Args:
            title (str): Title to get date from and clean
            get_date_from_title (bool): Whether to remove dates from title. Defaults to False.

        Returns:
            Tuple[str,Optional[datetime],Optional[datetime]]: Cleaned title, start and end dates

        """
        startdate = None
        enddate = None
        title = title.strip()
        if not get_date_from_title:
            return title, startdate, enddate

        match = cls.YEAR_RANGE_PATTERN.search(title)
        if match is not None:
            startdate = parse_date('%s-01-01' % match.group(1), '%Y-%m-%d')
            enddate = parse_date('%s-12-31' % match.group(2), '%Y-%m-%d')
            newtitle = cls.remove(title, match.group(0))
            logger.info('Removing date range from title: %s -> %s' % (title, newtitle))
            title = newtitle

        match = cls.BETWEEN_BRACKETS_PATTERN.search(title)
        if match is not None:
            string, sd, ed = cls.fuzzy_match(match.group(1))
            if sd:
                newtitle = cls.remove(title, match.group(0))
                logger.info('Removing date between brackets from title: %s -> %s' % (title, newtitle))
                title = newtitle
                if startdate is None:
                    startdate = sd
                    enddate = ed

        match = cls.YEAR_TWICE_PATTERN.search(title)
        if match is not None:
            first_year = match.group(1)
            second_year = match.group(2)
            first_startdate = parse_date('%s-01-01' % first_year, '%Y-%m-%d')
            second_startdate = parse_date('%s-01-01' % second_year, '%Y-%m-%d')
            if first_startdate > second_startdate:
                startdate = second_startdate
                enddate = parse_date('%s-12-31' % second_year, '%Y-%m-%d')
            else:
                startdate = first_startdate
                enddate = parse_date('%s-12-31' % first_year, '%Y-%m-%d')
            newtitle = cls.remove(title, first_year)
            newtitle = cls.remove(newtitle, second_year)
            logger.info('Removing two year values from title: %s -> %s' % (title, newtitle))
            title = newtitle

        newtitle, sd, ed = cls.fuzzy_match(title)
        if sd:
            logger.info('Removing date from title: %s -> %s' % (title, newtitle))
            title = newtitle
            if startdate is None:
                startdate = sd
                enddate = ed

        title = remove_from_end(title, ['-', 'as of'], 'Removing - from title: %s -> %s')
        return title, startdate, enddate

    def generate_dataset_and_showcase(self, countryiso, layer, maintainerid, orgid, orgname, updatefreq='Adhoc',
                                      subnational=True, get_date_from_title=False, process_dataset_name=lambda x: x):
        # type: (str, Dict, str, str, str, str, bool, bool, Callable[[str], str]) -> Tuple[Optional[Dataset],Optional[Showcase]]
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
            get_date_from_title (bool): Whether to remove dates from title. Defaults to False.
            process_dataset_name (Callable[[str], str]): Function to change the dataset name. Defaults to lambda x: x.

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

        oldtitle = title
        title, startdate, enddate = self.get_date_from_title(title, get_date_from_title)
        logger.info('Creating dataset: %s' % title)
        detail_url = layer['detail_url']
        supplemental_information = layer['supplemental_information']
        if supplemental_information.lower()[:7] == 'no info':
            dataset_notes = notes
        else:
            dataset_notes = '%s\n\n%s' % (notes, supplemental_information)
        if oldtitle != title:
            dataset_notes = '%s\n\nOriginal dataset title: %s' % (dataset_notes, oldtitle)
        slugified_name = slugify('%s_geonode_%s' % (orgname, title))
        slugified_name = process_dataset_name(slugified_name)
        dataset = Dataset({
            'name': slugified_name,
            'title': title,
            'notes': dataset_notes
        })
        dataset.set_maintainer(maintainerid)
        dataset.set_organization(orgid)
        if startdate is None:
            startdate = parse_date(layer['date'])
        dataset.set_dataset_date_from_datetime(startdate, dataset_end_date=enddate)
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
        return dataset, showcase

    def generate_datasets_and_showcases(self, maintainerid, orgid, orgname, updatefreq='Adhoc', subnational=True,
                                        create_dataset_showcase=create_dataset_showcase, countrydata=None,
                                        get_date_from_title=False, process_dataset_name=lambda x: x):
        # type: (str, str, str, str, bool, Callable[[Dataset, Showcase], None], Dict[str,Optional[str]], bool, Callable[[str], str]) -> List[Dataset]
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
            get_date_from_title (bool): Whether to remove dates from title. Defaults to False.
            process_dataset_name (Callable[[str], str]): Function to change the dataset name. Defaults to lambda x: x.

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
                                                                       orgname, updatefreq, subnational,
                                                                       get_date_from_title, process_dataset_name)
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
            if not any(x in dataset.get_resource()['url'] for x in self.geonode_urls):
                continue
            logger.info('Deleting %s' % dataset['title'])
            delete_from_hdx(dataset)
