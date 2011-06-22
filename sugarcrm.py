
import SOAPpy
import hashlib
import types
import time
from Crypto.Cipher import DES3
import itertools


class SugarError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


class SugarInstance:
    """This is a connection to a SugarCRM server."""
    
    def __init__(self, url, username, password, modules, ldap_passwd, ldap_iv):
        self.url = url
        self.username = username
        self.password = password
        
        self.wsdl = SOAPpy.WSDL.Proxy(url)
#        self.wsdl.soapproxy.config.dumpSOAPOut = 1
#        self.wsdl.soapproxy.config.dumpSOAPIn = 1
        
        if ldap_passwd == '' or ldap_iv == '':
            password_hash = hashlib.md5()
            password_hash.update(password)
            digest = password_hash.hexdigest()
        else:
            # Use the ldap_key to create the cipher used to encrypt the user
            # password.
            ldap_key = hashlib.md5(ldap_passwd).hexdigest()[:24]
            cipher = DES3.new(ldap_key, DES3.MODE_CBC, ldap_iv)
        
            # Encrypt the LDAP hash to get an hexadecimal representation
            ciphertext_bin = cipher.encrypt(password)
            ciphertext_hex = ''
            for byte in ciphertext_bin:
                ciphertext_hex += "%02x" % ord(byte)
            digest = ciphertext_hex
        
        result = self.wsdl.login({'user_name': username,
                            'password': digest,
                            'version': '0.1'}, 'Sugar.py')
        
        self.session = result['id']
        
        self.modules = {}
        for module in modules:
            self.modules[module] = SugarModule(self, module)
    
    def relate(self, main, secondary):
        rel = {}
        rel['module1'] = main.module.module_name
        rel['module1_id'] = main['id']
        rel['module2'] = secondary.module.module_name
        rel['module2_id'] = secondary['id']
        
        self.wsdl.set_relationship(self.session, rel)


class SugarModule:
    """Defines a SugarCRM module."""
    
    def __init__(self, instance, module_name):
        self.module_name = module_name
        self.instance = instance
        
        # Get the module fields through SugarCRM API.
        result = self.instance.wsdl.get_module_fields(self.instance.session,
                                                         self.module_name)

        self.fields = result['module_fields']


    def search(self, query_str, start = 0, total = 20, fields = []):
        """Returns a list of SugarCRM entries that match the query."""

        if 'id' not in fields:
            fields.append('id')
        
        entry_list = []
        count = 0
        offset = 0
        while count < total:
            result = self.instance.wsdl.get_entry_list(
                            self.instance.session, self.module_name,
                            query_str, '', start + offset, fields,
                            total - count, 0)
            if result['result_count'] == 0:
                break
            else:
                offset += result['result_count']
                for i in range(result['result_count']):
                    
                    new_entry = SugarEntry(self)
                    
                    for attribute in result['entry_list'][i]['name_value_list']:
                        new_entry.fields[attribute['name']] = attribute['value']
            
                    # SugarCRM seems broken, because it retrieves several copies
                    #  of the same contact for every opportunity related with
                    #  it. Check to make sure we don't return duplicate entries.
                    if new_entry['id'] not in [entry['id'] for entry in entry_list]:
                        entry_list.append(new_entry)
                        count += 1
        
        return entry_list


    def query(self):
        return QueryList(self)


class SugarEntry:
    """Defines an entry of a SugarCRM module."""
    
    def __init__(self, module):
        """Represents a new or an existing entry."""

        # Keep a reference to the parent module.
        self.module = module
        
        # Keep a mapping 'field_name' => value for every valid field retrieved.
        self.fields = {}
        self.dirty_fields = []
        
        # Make sure that the 'id' field is always defined.
        if 'id' not in self.fields.keys():
            self.fields['id'] = ''
    

    def __getitem__(self, field_name):
        """Value to return when self['field_name'] is used."""
        if field_name in [item['name'] for item in self.module.fields]:
            try:
                return self.fields[field_name]
            except KeyError:
                if self['id'] == '':
                    # If this is a new entry, the 'id' field is yet undefined.
                    return ''
                else:
                    # Retrieve the field from the SugarCRM instance.
                    
                    q_str = self.module.module_name.lower() + \
                                ".id='%s'" % self['id']
                    res = self.module.instance.wsdl.get_entry_list(
                            self.module.instance.session,
                            self.module.module_name,
                            q_str, '', 0, [field_name], 1, 0)
                    for attribute in res['entry_list'][0]['name_value_list']:
                        if attribute['name'] == field_name:
                            self.fields[attribute['name']] = attribute['value']
                            return attribute['value']

        else:
            raise AttributeError


    def __setitem__(self, field_name, value):
        if field_name in [item['name'] for item in self.module.fields]:
            self.fields[field_name] = value
            if field_name not in self.dirty_fields:
                self.dirty_fields.append(field_name)
        else:
            raise AttributeError


    def save(self):
        """Saves this entry in SugarCRM through SOAP. If the 'id' field is
        blank, it creates a new entry and sets the 'id' value."""
        
        # If 'id' wasn't blank, it's added to the list of dirty fields; this
        # way the entry will be updated in the SugarCRM instance.
        if self['id'] != '':
            self.dirty_fields.append('id')
        
        # nvl is the name_value_list, which has the list of attributes.
        nvl = []
        for field in set(self.dirty_fields):
            # Define an individual name_value record.
            nv = {}
            nv['name'] = field
            nv['value'] = self[field]
            nvl.append(nv)
        
        # Use the API's set_entry to update the entry in SugarCRM.
        result = self.module.instance.wsdl.set_entry(
                                                self.module.instance.session,
                                                self.module.module_name, nvl)
        self.fields['id'] = result['id']
        self.dirty_fields = []

        return True


    def relate(self, related):
        self.module.instance.relate(self, related)


class QueryList():

    def __init__(self, module):
        self._module = module
        self._query = ''
        self._next_items = []
        self._offset = 0


    def __iter__(self):
        return self


    def next(self):
        try:
            item = self._next_items[0]
            self._next_items = self._next_items[1:]
            return item
        except IndexError:
            self._next_items = self._module.search(self._query,
                                                start = self._offset, total = 5)
            self._offset += len(self._next_items)
            if len(self._next_items) == 0:
                raise StopIteration
            else:
                return self.next()

    def __getitem__(self, index):
        try:
            return next(itertools.islice(self, index, index + 1))
        except TypeError:
            return list(itertools.islice(self, index.start, index.stop,
                                            index.step))



    def build_query(self, **query):
        # Build the API query string
        q_str = ''
        for key in query.keys():
            # Get the field and the operator from the query
            key_field, key_sep, key_oper = key.partition('__')
            if q_str != '':
                q_str += ' AND '

            if_cstm = ''
            if key_field.endswith('_c'):
                if_cstm = '_cstm'

            field = self._module.module_name.lower() + if_cstm + '.' + key_field

            if key_oper == 'exact':
                q_str += '%s = "%s"' % (field, query[key])
            elif key_oper == 'contains':
                q_str += '%s LIKE "%%%s%%"' % (field, query[key])
            elif key_oper == 'in':
                q_str += '%s IN (' % field
                for elem in query[key]:
                    q_str += "'%s'," % elem
                q_str = q_str.rstrip(',')
                q_str += ')'
            elif key_oper == 'gt':
                q_str += '%s > "%s"' % (field, query[key])
            elif key_oper == 'gte':
                q_str += '%s >= "%s"' % (field, query[key])
            elif key_oper == 'lt':
                q_str += '%s < "%s"' % (field, query[key])
            elif key_oper == 'lte':
                q_str += '%s <= "%s"' % (field, query[key])
            else:
                raise LookupError('Unsupported operator')

        return q_str


    def filter(self, **query):
        if self._query != '':
            self._query = '(%s) AND (%s)' % (self._query,
                                            self.build_query(**query))
        else:
            self._query = self.build_query(**query)


    def exclude(self, **query):
        if self._query != '':
            self._query = '(%s) AND NOT (%s)' % (self._query,
                                            self.build_query(**query))
        else:
            self._query = 'NOT (%s)' % self.build_query(**query)


