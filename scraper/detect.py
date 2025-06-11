'''
In this file we detect the product cards
inside the target page.
'''

from urllib.parse import urlparse, urlunparse
from collections import Counter
from bs4 import BeautifulSoup, Tag
from typing import Optional, Tuple, Dict, List, Union, cast

import scraper.parse as parse



class ProductCardDetector:
    '''
    Amazon has different layouts for different
    product pages. also they use different css
    and html structure for them. on top of that
    they also change these layouts from time to
    time. thats why we look for repetative patterns
    inside ONLY product containers. 
    forexample repetative div tags that have the same
    structure inside a product or grid container.
    this way we arent relying on concrete css
    or html.
    '''
    def __init__(self, url_keywords, soup):
        self.keywords = url_keywords
        self.soup : BeautifulSoup = soup
        self.grid_containers = self.soup.find_all(
            class_=lambda x: bool(x) and any(
                c in str(x).lower() 
                for c in ['grid', 'results', 'items', 'products', 'card']
            )
        )

    def get_structure_signature(self, tag : Tag) -> Tuple[str, ...]:
        '''
        Gets the html structure of the given tag by
        extracting its direct children names.
        Args:
        tag : bs4 Tag object
        Returns:
        A tuple of strings representing the structures signature
        '''
        # Holds the names of direct child elements of the tag
        tags = []
        for child in tag.find_all(recursive=False):
            if isinstance(child, Tag) and child.name:
                tags.append(child.name)
        
        return tuple(tags)

    def get_class_signature(self, tag : Tag) -> Tuple[str, ...]:
        '''
        Gets the class signature of the given tag.
        Args:
            tag : bs4 Tag object
        Returns:
            A tuple of class names sorted alphabetically.
        '''
        class_attr : Union[str, List[str], None] = tag.get("class")
        
        # The case where it may be None
        if class_attr is None:
            return tuple()
        
        # The case where it may be str
        if isinstance(class_attr, str):
            return tuple(class_attr,)
        
        # if its neither, then its a List[str]
        classes = cast(List[str], class_attr)
        
        return tuple(sorted(classes))
    
    def _visible(self, container : Tag) -> bool:
        ''' Gets a container and checks its visibility.
        Args:
            - container: The container to check.
        Returns:
            - True if the container is visible, False otherwise.
        '''
        style_attr = container.get('style', '')
        style = str(style_attr) if style_attr is not None else ''
        normalized_style = style.replace(' ', '').lower()

        aria_hidden = str(container.get('aria-hidden', '')).lower()

        if 'display:none' in normalized_style:
            return False
        if aria_hidden == "true":
            return False
         
        return True

    def find_mostcommon_signiture(
            self
            ) -> Tuple[List[Tuple[str, ...]], List[Tuple[str, ...]]]:
        ''' 
        Finds the top 3 most common structure and class signatures
        in the grid containers using the soup object passed to the
        class.
        
        Returns:
            - most_common_structures: List of tuples containing the most common structure signatures
            - most_common_classes: List of tuples containing the most common class signatures
        '''
        
        structure_signatures : list[tuple] = []
        class_signatures : list[tuple] = []

        for container in self.grid_containers:
            if isinstance(container, Tag):
                for div in container.find_all("div"):
                    if not isinstance(div, Tag):
                        continue

                    structure_signature = self.get_structure_signature(div)
                    class_signature = self.get_class_signature(div)
                    
                    if len(structure_signature) >= 3 and structure_signature not in [('label',), ('i', 'span')]:
                        structure_signatures.append(structure_signature)
                        class_signatures.append(class_signature)


        most_common_structures = [s for s,_ in Counter(structure_signatures).most_common(3)]
        most_common_classes = [c for c,_ in Counter(class_signatures).most_common(3)]

        return most_common_structures, most_common_classes

    def is_product_card(
            self, tag : Tag,
            most_common_structures,
            most_common_classes
            ) -> bool:
        '''Gets the structure and class signatures of the tag
        and checks if they match the most common signatures.
        Also checks if the tag has a price, image, and title.
        if it doesnt have these 3, then it is not a product card.
        Args:
        most_common_structures: The most common structure signatures
        most_common_classes: The most common class signatures
        Returns:
        True if the tag is a product card, False otherwise.'''
        
        if not self._visible(tag):
            return False

        tag_structure = self.get_structure_signature(tag)
        tag_class = self.get_class_signature(tag)

        # Signature matching
        tag_match : bool = tag_structure in most_common_structures
        class_match : bool = tag_class in most_common_classes

        has_price = bool(tag.find(string=lambda text: '$' in str(text)))
        has_image = bool(tag.find('img'))
        has_title = bool(tag.find(['h2', 'h3', 'h4', 'span', 'div'], 
                           class_=lambda x: bool(x) and any(c in str(x).lower() for c in ['title', 'name'])))
        
        is_product = (has_price + has_image + has_title) >= 2

        return (tag_match or class_match) and is_product
    
    def get_all_product_cards(self) -> List[Dict[str, Union[bool, Optional[str], List[Dict[str, Optional[str]]]] ]]:
        '''
        This method acts as a facade for the users of this class.
        it hides the complexity of finding the product cards.
        It guarantees that the products found, dont have missing
        data by applying the extract data and extract data fallback
        logic form parse.
        Returns:
            A list of dictionaries containing the product cards.
        '''

        product_cards : List[Dict[str, Union[bool, Optional[str], List[Dict[str, Optional[str]]]] ]] = []
        seen_asins = set()
        
        most_common_structures, most_common_classes = self.find_mostcommon_signiture()

        if not most_common_structures or not most_common_classes:
            return product_cards

        for container in self.grid_containers:
            if isinstance(container, Tag):
                container_divs = container.find_all("div", recursive=True)
                for div in container_divs:
                    if not isinstance(div, Tag):
                        continue

                    if self.is_product_card(div, most_common_structures, most_common_classes):
                        data : Dict[str, Union[bool, Optional[str], List[Dict[str, Optional[str]]]]] = parse.extract_data(div)
                        
                        if data: #and data.get('link'):
                            if data['asin'] not in seen_asins:
                                seen_asins.add(data['asin'])

                                if data['_needs_fallback']:
                                    try:
                                        data : Dict[str, Union[bool, Optional[str], List[Dict[str, Optional[str]]]]] = parse.extract_data_fallback(
                                            data, str(data.get('link')))
                                    except Exception as e:
                                        print(f'fallback Failed for {data["link"]} error:\n{e}')
                                        continue
                        
                                product_cards.append(data)

                                # Test with 10
                                if len(product_cards) >= 10:
                                    print('length 10 reached')
                                    return product_cards
        
        return product_cards