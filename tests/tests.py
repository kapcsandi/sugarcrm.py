
#    Copyright 2011 Luis Barrueco
#
#    This file is part of sugarcrm.py.
#
#    sugarcrm.py is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    sugarcrm.py is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with sugarcrm.py.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
sys.path.insert(1, "..")

import unittest

import sugarcrm
import crm_config
import uuid

newuuid = uuid.uuid4()

class TestSugarPy(unittest.TestCase):

    def setUp(self):
        self.instance = sugarcrm.SugarInstance(crm_config.WSDL_URL,
                            crm_config.USERNAME,
                            crm_config.PASSWORD, ['Contacts', 'Leads'],
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

    def test_query(self):
        q = self.instance.modules['Contacts'].query()
        q = q.filter(first_name__exact=self.entry['first_name'])
        self.assertNotEqual(q, [])

    def test_related(self):
        new_lead = sugarcrm.SugarEntry(self.instance.modules['Leads'])
        new_lead['first_name'] = 'Juan'
        new_lead['last_name'] = 'Perez'
        new_lead['status'] = 'New'
        new_lead.save()

        self.entry.relate(new_lead)

        leads = self.entry.get_related('Leads')
        self.assertEqual(new_lead['id'], leads[0]['id'])
        new_lead['deleted'] = True
        new_lead.save()


if __name__ == '__main__':
    unittest.main()

