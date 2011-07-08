
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

import sugarcrm

# This is the URL for the wsdl resource in your SugarCRM instance.
WSDL_URL = 'http://127.0.0.1/sugarcrm/service/v4/soap.php?wsdl'
USERNAME = 'admin'
PASSWORD = 'password'

# Leave these two parameters blank if you're not using LDAP authentication.
LDAP_PASSWD = ''
LDAP_IV = ''

# This way you log-in to your SugarCRM instance. You must specify the list of
# modules you are planning to access.
instance = sugarcrm.SugarInstance(WSDL_URL, USERNAME, PASSWORD,
                                    ['Contacts', 'Cases'], LDAP_PASSWD, LDAP_IV)

# This way you query all the Contacts in your database...
query = instance.modules['Contacts'].query()
# ... but we just show the first ten of them.
for contact in query[:10]:
    print contact['first_name'] + ' ' + contact['last_name']

# OUTPUT:
# Darrin Adger
# Gilbert Adkins
# Maritza Bail
# Morris Balmer
# Polly Barahona
# Claude Barksdale
# Merrill Barragan
# Aimee Bassler
# Rosario Bassler
# Gil Batten

# We define a new query, but this time we specify a couple of query exclusions.
query = instance.modules['Contacts'].query()
new_query = query.exclude(last_name__exact = 'Bassler')
new_query = new_query.exclude(first_name__exact = 'Morris')
for contact in new_query[:10]:
    print contact['first_name'] + ' ' + contact['last_name']

# OUTPUT:
# Darrin Adger
# Gilbert Adkins
# Maritza Bail
# Polly Barahona
# Claude Barksdale
# Merrill Barragan
# Gil Batten
# Rodrigo Baumeister
# Lakesha Bernhard
# Bryon Bilbo

# This new query has a filter. Please notice that the filter parameter is the
# field name in the SugarCRM module, followed by a double underscore, and then
# an operator (it can be 'exact', 'contains', 'gt', 'gte', 'lt', 'lte' or 'in').
new_query = query.filter(last_name__contains='ass')
for contact in new_query[:10]:
    print contact['first_name'] + ' ' + contact['last_name']

# OUTPUT:
# Aimee Bassler
# Rosario Bassler
# Blake Cassity
# Ann Hassett

new_query = query.filter(last_name__in=['Bassler', 'Everitt'])
for contact in new_query[:10]:
    print contact['first_name'] + ' ' + contact['last_name']

# OUTPUT:
# Aimee Bassler
# Rosario Bassler
# Stanford Everitt

query = instance.modules['Cases'].query()
new_query = query.filter(case_number__lt='7')
for case in new_query[:10]:
    print case['case_number'] + ' / ' + case['name'] + ' / ' + case['description']

# OUTPUT:
# 1 / Having trouble adding new items / 
# 2 / Warning message when using the wrong browser / 
# 3 / Having trouble adding new items / 
# 4 / Having trouble adding new items / 
# 5 / Need assistance with large customization / 
# 6 / Need to purchase additional licenses / 


# Search the first case and relate it to the first contact
query = instance.modules['Cases'].query()
case = query[0]
query = instance.modules['Contacts'].query()
query = query.filter(last_name__exact = 'Adger')
contact = query[0]
case.relate(contact)

case.get_related('Contacts')

# OUTPUT:
# [<SugarCRM Contact entry 'Darrin Adger'>]

# 'contact' holds a Contacts entry with last name 'Adger'. We can modify some
# fields and then save it
contact['birthdate'] = '1978-05-10'
contact.save()

