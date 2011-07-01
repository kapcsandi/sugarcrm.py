
import SOAPpy
import hashlib
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
        self._url = url
        self._username = username
        self._password = password
        
        self._wsdl = SOAPpy.WSDL.Proxy(url)
#        self._wsdl.soapproxy.config.dumpSOAPOut = 1
#        self._wsdl.soapproxy.config.dumpSOAPIn = 1
        
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
        
        result = self._wsdl.login({'user_name': username,
                            'password': digest,
                            'version': '0.1'}, 'Sugar.py')
        
        self._session = result['id']
        
        self.modules = {}
        for module in modules:
            self.modules[module] = SugarModule(self, module)
    
    def relate(self, main, secondary):
        """Relate two SugarEntry objects."""

        self._wsdl.set_relationship(self._session, main._module._module_name,
                            main['id'], secondary._module._module_name.lower(),
                            [secondary['id']])


class SugarModule:
    """Defines a SugarCRM module."""
    
    def __init__(self, instance, module_name):
        self._module_name = module_name
        self._instance = instance
        
        # Get the module fields through SugarCRM API.
        result = self._instance._wsdl.get_module_fields(self._instance._session,
                                                         self._module_name)

        self._fields = result['module_fields']


    def search(self, query_str, start = 0, total = 20, fields = []):
        """Return a list of SugarEntry objects that match the query."""

        if 'id' not in fields:
            fields.append('id')
        
        entry_list = []
        count = 0
        offset = 0
        while count < total:
            result = self._instance._wsdl.get_entry_list(
                            self._instance._session, self._module_name,
                            query_str, '', start + offset, fields,
                            total - count, 0)
            if result['result_count'] == 0:
                break
            else:
                offset += result['result_count']
                for i in range(result['result_count']):
                    
                    new_entry = SugarEntry(self)
                    
                    for attribute in result['entry_list'][i]['name_value_list']:
                        new_entry._fields[attribute['name']] = attribute['value']
            
                    # SugarCRM seems broken, because it retrieves several copies
                    #  of the same contact for every opportunity related with
                    #  it. Check to make sure we don't return duplicate entries.
                    if new_entry['id'] not in [entry['id'] for entry in entry_list]:
                        entry_list.append(new_entry)
                        count += 1
        
        return entry_list


    def query(self):
        """
        Return a QueryList object for this SugarModule. Initially, it describes
        all the objects in the module. One can find specific objects by
        calling 'filter' and 'exclude' on the returned object.
        """

        return QueryList(self)


class SugarEntry:
    """Defines an entry of a SugarCRM module."""
    
    def __init__(self, module):
        """Represents a new or an existing entry."""

        # Keep a reference to the parent module.
        self._module = module
        
        # Keep a mapping 'field_name' => value for every valid field retrieved.
        self._fields = {}
        self._dirty_fields = []
        
        # Make sure that the 'id' field is always defined.
        if 'id' not in self._fields.keys():
            self._fields['id'] = ''


    def __repr__(self):
        return "<SugarCRM %s entry '%s'>" % \
                    (self._module._module_name.rstrip('s'), self['name'])


    def __getitem__(self, field_name):
        """Return the value of the field 'field_name' of this SugarEntry."""

        if field_name in [item['name'] for item in self._module._fields]:
            try:
                return self._fields[field_name]
            except KeyError:
                if self['id'] == '':
                    # If this is a new entry, the 'id' field is yet undefined.
                    return ''
                else:
                    # Retrieve the field from the SugarCRM instance.
                    
                    q_str = self._module._module_name.lower() + \
                                ".id='%s'" % self['id']
                    res = self._module._instance._wsdl.get_entry_list(
                            self._module._instance._session,
                            self._module._module_name,
                            q_str, '', 0, [field_name], 1, 0)
                    for attribute in res['entry_list'][0]['name_value_list']:
                        if attribute['name'] == field_name:
                            self._fields[attribute['name']] = attribute['value']
                            return attribute['value']

        else:
            raise AttributeError


    def __setitem__(self, field_name, value):
        """Set the value of the field 'field_name' of this SugarEntry."""

        if field_name in [item['name'] for item in self._module._fields]:
            self._fields[field_name] = value
            if field_name not in self._dirty_fields:
                self._dirty_fields.append(field_name)
        else:
            raise AttributeError


    def save(self):
        """Saves this entry in SugarCRM through SOAP. If the 'id' field is
        blank, it creates a new entry and sets the 'id' value."""
        
        # If 'id' wasn't blank, it's added to the list of dirty fields; this
        # way the entry will be updated in the SugarCRM instance.
        if self['id'] != '':
            self._dirty_fields.append('id')
        
        # nvl is the name_value_list, which has the list of attributes.
        nvl = []
        for field in set(self._dirty_fields):
            # Define an individual name_value record.
            nv = {}
            nv['name'] = field
            nv['value'] = self[field]
            nvl.append(nv)
        
        # Use the API's set_entry to update the entry in SugarCRM.
        result = self._module._instance._wsdl.set_entry(
                                                self._module._instance._session,
                                                self._module._module_name, nvl)
        self._fields['id'] = result['id']
        self._dirty_fields = []

        return True


    def relate(self, related):
        """Relate this SugarEntry with the one passed as a parameter."""

        self._module._instance.relate(self, related)


    def get_related(self, module_name):
        """Return the related entries in the module 'module_name'"""

        instance = self._module._instance
        result = instance._wsdl.get_relationships(instance._session,
                            self._module._module_name, self['id'],
                            module_name.lower())

        entries = []
        for elem in result['entry_list']:
            entry = SugarEntry(instance.modules[module_name])
            entry._fields['id'] = elem['id']
            entries.append(entry)

        return entries

class QueryList():
    """Query a SugarCRM module for specific entries."""

    def __init__(self, module, query = ''):
        self._module = module
        self._query = query
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



    def _build_query(self, **query):
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

            field = self._module._module_name.lower() + if_cstm + '.' + key_field

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
        """Filter this QueryList, returning a new QueryList.

        query is a keyword argument dictionary where the filters are specified:
        The keys should be some of the module's field names, suffixed by '__'
        and one of the following operators: 'exact', 'contains', 'in', 'gt',
        'gte', 'lt' or 'lte'. When the operator is 'in', the corresponding value
        MUST be a list.
        """

        if self._query != '':
            query = '(%s) AND (%s)' % (self._query, self._build_query(**query))
        else:
            query = self._build_query(**query)

        return QueryList(self._module, query)


    def exclude(self, **query):
        """Filter this QueryList, returning a new QueryList, as in filter(), but
        excluding the entries that match the query.
        """

        if self._query != '':
            query = '(%s) AND NOT (%s)' % (self._query, self._build_query(**query))
        else:
            query = 'NOT (%s)' % self._build_query(**query)

        return QueryList(self._module, query)


