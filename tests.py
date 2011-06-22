
import unittest

import sugarcrm
import crm_config
import uuid

newuuid = uuid.uuid4()

class TestSugarPy(unittest.TestCase):

    def setUp(self):
        self.instance = sugarcrm.SugarInstance(crm_config.WSDL_URL,
                            crm_config.USERNAME,
                            crm_config.PASSWORD, ['Contacts'],
                            crm_config.LDAP_PASSWD, crm_config.LDAP_IV)
        
        self.entry = sugarcrm.SugarEntry(self.instance.modules['Contacts'])
        
        self.entry['first_name'] = str(newuuid)
        self.entry['last_name'] = 'Perez'
        self.entry.save()

    def tearDown(self):
        self.entry['deleted'] = True
        self.entry.save()

    def test_setattr_getattr(self):
        self.entry['first_name'] = 'Juan'
        self.entry.save()
        self.assertEqual(self.entry['first_name'], 'Juan')

    def test_search(self):
        res = self.instance.modules['Contacts'].search(
                            "contacts.first_name='%s'" % str(newuuid))
        self.assertEqual(len(res), 1)


if __name__ == '__main__':
    unittest.main()

