#!/usr/bin/python

# This script is intended to populate the MESS Database for the first time.
# It accepts a .tsv file exported from Excel.
# 
# Currently this script only imports members in Section 1.0 (active) and 
# Section 4.0 (multi-member information).  All other sections are SKIPPED.
#
#
# Beware: Some accounts get imported incorrectly, and must be fixed
# by hand after importing.


# mess should be symlinked from /usr/lib/python2.4/site-packages
# sys.path.insert(0, '/home/paul/mess/trunk')
from mess import settings
from django.core.management import setup_environ
setup_environ(settings)

# these imports seem to raise errors if placed before setup_environ(settings)
import sys
import os
import codecs
import string
import time
import re
from random import choice
from mess.membership.models import Member, Account
from mess.profiles.models import UserProfile, Address, Phone, Email
#from mess.utils.person_to_user import slug_name, generate_pass, save_user
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.db import IntegrityError

MAXLINES = 20000    # only import first N members for debugging


def refine_mem_data(dat, column):
    ''' fills available information into mem dict '''
    if dat == {}:
        dat = {'first_name': 'Firstname', 
               'last_name': 'Lastname', 
               'has_keycard': 'No', 
               'date_joined': '1900-01-01',
               'email': '',
               'address_street': '',
               'address_city': '',
               'address_state': '',
               'address_zip': '',
               'phone': '',
               'second_phone': '',
               'contact_preference': 'e',
               'card_number': '',
               'card_facility_code': '',
               'card_type': '',
               'cumul_deposit': '',
              }
    if column['Member'] != '':
        dat['first_name'], dat['last_name'] = split_name(column['Member'])
    if column['Has key?'] != '':
        dat['has_keycard'] = column['Has key?'] 
    if column['Join Date'] != '':
        dat['date_joined'] = dateformat(column['Join Date'])
    if column['email'] != '':
        dat['email'] = column['email']
    if column['Street Address & Apt / City State / ZIP'] != '':
        dat['address_street'], dat['address_city'], dat['address_state'], dat['address_zip'] = split_address(column['Street Address & Apt / City State / ZIP'])
    if column['phone #'] != '':
        dat['phone'] = column['phone #']
    if column['second phone #'] != '':
        dat['second_phone'] = column['second phone #']
    if column['which contact preferred'] != '':
        dat['contact_preference'] = column['which contact preferred']
    if column['Card Number'] != '':
        dat['card_number'] = column['Card Number']
    if column['Card Facility Code'] != '':
        dat['card_facility_code'] = column['Card Facility Code']
    if column['Card Type'] != '':
        dat['card_type'] = column['Card Type']
    # only record deposit under member if it's recorded in section 4.0
    if column['$ cumulative deposit'] != '' and column['Section'] == '4.0':
        dat['cumul_deposit'] = column['$ cumulative deposit']
    return dat

def second_shopper_data(column):
    ''' fills a minimalist mem dict with second_shopper data '''
    dat = {'first_name': 'Firstname', 
               'last_name': 'Lastname', 
               'has_keycard': 'No', 
               'date_joined': '1900-01-01',
               'email': '',
               'address_street': '',
               'address_city': '',
               'address_state': '',
               'address_zip': '',
               'phone': '',
               'second_phone': '',
               'contact_preference': 'e',
               'card_number': '',
               'card_facility_code': '',
               'card_type': '',
               'cumul_deposit': '',
              }
    dat['first_name'], dat['last_name'] = split_name(
                   column['Second Authorized Shopper'])
    dat['phone'] = column['Second Authorized Shopper #']
    return dat


def get_mems(column):
    ''' returns a list of mems, len = column['Active Members'] '''
    ret = [refine_mem_data({}, column) for i in 
                                        range(int(column['Active Members']))]
    if ';' in column['Member']:
        for i, mem in enumerate(column['Member'].split(';',len(ret)-1)):
            ret[i]['first_name'], ret[i]['last_name'] = split_name(mem)
    if column['Second Authorized Shopper'] != '':
        ret[0]['second_shopper'] = second_shopper_data(column)
    return ret


# utility functions from person_to_user.py
alpha_not = re.compile(r'\W')
def slug_name(name):
    alpha = alpha_not.sub('', name)
    lowered = alpha.lower()
    if len(lowered) > 8:
        sliced = lowered[:8]
    else:
        sliced = lowered
    return sliced

def generate_pass():
    return ''.join([choice(string.letters+string.digits) for i in range(8)])

def save_user(user, slug, count):
    try:
        user.save()
    except IntegrityError:
        new_name = slug + str(count)
        user.username = new_name
        count += 1
        save_user(user, slug, count)


# utility functions
def split_address(addstr):
    ''' Street Address & Apt / City State / ZIP '''
    addr = addstr.rsplit('/',2)
    if len(addr) == 3:
        citystate = addr[1].strip().rsplit(None, 1)
        if len(citystate) < 2:
            return addstr, '', '', ''
        return addr[0].strip(), citystate[0].strip(), citystate[1].strip(), addr[2].strip()
    # if problem, return entire original string as street
    return addstr, '', '', ''

def dateformat(d):
    ''' for now, only fixes dates formatted as "June 15, 2008" '''
    try:
        return time.strftime('%Y-%m-%d',time.strptime(d,'"%B %d, %Y"'))
    except:
        return '1902-01-01'

def split_name(namestring):
    names = namestring.strip().rsplit(None,1)
    if len(names) == 1:
        return names[0], 'Lastname'
    return names[0], names[1]

def split_actstr(actstr):
    ''' try to split things like  "Best Fest NEEDS SHIFT" '''
    # find last lowercase character
    if actstr == '': return '', ''
    s = len(actstr) - 1
    while s >= 0 and actstr[s] not in unicode(string.lowercase):
        s -= 1
    while s < len(actstr) and actstr[s] not in unicode(string.whitespace):
        s += 1
    if s == len(actstr) - 1: return actstr.strip(), ''
    return actstr[:s].strip(), actstr[s:].strip()

def aprint(a):
    print unicode(a).encode('ascii','replace')



# actual importation code

# make sure a datafile argment was passed in
if len(sys.argv) < 2:
    print 'Usage:  '+sys.argv[0]+' datafile.tsv'
    sys.exit()

# convert any <85> (newline) characters embedded in the tsv file to spaces
os.system('tr \205 " " <'+sys.argv[1]+' >tempfile1')

# read in list of accounts and members
datafile = codecs.open('tempfile1', 'r', 'latin1')
acts = {}

print 'looping through data file...'
linenumber = 0
for line in datafile:
    linenumber += 1
    if linenumber == 1:
        infields = [x.strip() for x in line.split('\t')]
        infields[0] = 'Account'
        continue
    datum = [x.strip() for x in line.split('\t')]
    column = dict(zip(infields, datum))
    aprint (u'---reading line ['+str(linenumber)+'] '+
           column['Account'][:15] + u' Section:'+column['Section'])
    actname, actnotes = split_actstr(column['Account'])
    
    if column['Section'] == '1.0' and linenumber < MAXLINES:
        assert actname not in acts
        acts[actname] = {'mems': get_mems(column), 
            'actnotes': actnotes,
            'balance': column['Old Balance'],
            'cumul_deposit': column['$ cumulative deposit'],
            'flag_sec4': 0}
        print acts[actname]
        aprint('   imported account '+actname)

    elif column['Section'] == '4.0':
        if actname not in acts: 
            aprint('   SKIPPED section-4 member of nonexistent acct '+actname)
            continue
        print acts[actname]
        try:
            acts[actname]['mems'][acts[actname]['flag_sec4']] = (
            refine_mem_data(acts[actname]['mems'][acts[actname]['flag_sec4']],
            column))
        # if too many section-4 members, add extra members as 'inactive'
        except IndexError:
            acts[actname]['mems'].append(refine_mem_data({}, column))
            acts[actname]['mems'][acts[actname]['flag_sec4']]['status'] = 'i'
        if column['Second Authorized Shopper'] != '':
            acts[actname]['mems'][acts[actname]['flag_sec4']][
                    'second_shopper'] = second_shopper_data(column)
        acts[actname]['flag_sec4'] += 1
        print acts[actname]
        aprint('   imported section-4 member of account '+actname)

    else:
        aprint('   SKIPPED line')
        

    print

print 'Done Reading Input File! '

print 'Making authorized shoppers a type of member...'
for actname, ac in acts.iteritems():
    s = []
    for m in ac['mems']:
        if 'second_shopper' in m:
            s.append(m['second_shopper'])
    for m in s:
        m['status'] = '2'
        ac['mems'].append(m)


print 'Saving into database...'
for actname, ac in acts.iteritems():
    aprint('saving accountname '+actname)
    acct = Account()
    acct.name = actname
    # !! do something with ac['balance']
    # !! do something with ac['cumul_deposit']
    # !! do something with ac['actnotes']
    for i,m in enumerate(ac['mems']):
        user = User()
        user.first_name = m['first_name']
        user.last_name = m['last_name']
        user.username = slug_name(m['first_name']+m['last_name'])
        user.password = generate_pass()
        save_user(user, user.username, 0)
        print 'saved username : '+user.username

        profile = UserProfile()
        profile.user = user
        profile.save()

        if m['phone'] != '':
            phone = Phone()
            phone.number = m['phone'] 
            phone.save()
            profile.phones.add(phone)

        if m['second_phone'] != '':
            phone = Phone()
            phone.number = m['second_phone']
            phone.save()
            profile.phones.add(phone)

        if m['email'] != '':
            email = Email()
            email.email = m['email']
            email.save()
            profile.emails.add(email)

        if m['address_street'] != '':
            address = Address()
            address.address1 = m['address_street']
            address.city = m['address_city']
            address.state = m['address_state']
            address.postal_code = m['address_zip']
            address.save()
            profile.addresses.add(address)

        mem = Member()
        if m['has_keycard'] == 'Yes': 
            mem.has_key = True
        mem.contact_preference = m['contact_preference']
        mem.date_joined = m['date_joined']

        # !! do something with m['cumul_deposit']
        # !! do something with m['status']

        # link data structures together
        mem.user = user
        mem.primary_account = acct
        mem.save()
        if i == 0:
            acct.contact = mem
            acct.save()
        acct.members.add(mem)
    acct.save()


