from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core import paginator as p
from django.db.models import Q
from django.forms.models import modelformset_factory
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.template.loader import get_template

#from mess.accounting import models as a_models
from mess.membership import forms, models
from mess.scheduling import models as s_models
import datetime

# number of members or accounts to show per page in respective lists
PER_PAGE = 50

@user_passes_test(lambda u: u.is_authenticated())
def members(request):
    '''
    list of all members (active by default)
    '''
    if not request.user.is_staff:
        return HttpResponseRedirect(reverse('member', 
            args=[request.user.username]))
    context = RequestContext(request)
    members = models.Member.objects.all()
    if 'sort_by' in request.GET:
        form = forms.MemberListFilterForm(request.GET)
        if form.is_valid():
            search = form.cleaned_data.get('search')
            if search:
                members = members.filter(
                        Q(user__first_name__icontains=search) |
                        Q(user__last_name__icontains=search))
            sort = form.cleaned_data['sort_by']
            if sort == 'alpha':
                members = members.order_by('user__username')
            elif sort == 'oldjoin':
                members = members.order_by('date_joined')
            elif sort == 'newjoin':
                members = members.order_by('-date_joined')
            if not form.cleaned_data['active']:
                members = members.exclude(date_missing__isnull=True,
                        date_departed__isnull=True)
            if not form.cleaned_data['missing']:
                members = members.exclude(date_missing__isnull=False)
            if not form.cleaned_data['departed']:
                members = members.exclude(date_departed__isnull=False)
    else:
        form = forms.MemberListFilterForm()
        members = members.filter(date_missing__isnull=True,
                date_departed__isnull=True)
    context['form'] = form
    pager = p.Paginator(members, PER_PAGE)
    context['pager'] = pager
    page_number = request.GET.get('p')
    context['page'] = _get_current_page(pager, page_number)
    # drop any p= queries from the query string
    context['query_string'] = request.META['QUERY_STRING'].split('&p=', 1)[0]
    template = get_template('membership/members.html')
    return HttpResponse(template.render(context))

@user_passes_test(lambda u: u.is_authenticated())
def member(request, username):
    '''
    individual member page
    '''
    user = get_object_or_404(User, username=username)
    if not request.user.is_staff and not (request.user.is_authenticated() 
            and request.user.id == user.id):
        return HttpResponseRedirect(reverse('login'))
    context = RequestContext(request)
    context['member'] = user.get_profile()
    # to get around silly {% url %} limits
    context['address_name'] = 'address'
    context['email_name'] = 'email'
    context['phone_name'] = 'phone'
    context['contact_media'] = ['address', 'email', 'phone']
    template = get_template('membership/member.html')
    return HttpResponse(template.render(context))

@user_passes_test(lambda u: u.is_staff)
def member_form(request, username=None):
    '''
    edit member info
    '''
    if username:
        user = get_object_or_404(User, username=username)
        member = user.get_profile()
    else:
        user = User()
        member = models.Member()
    is_errors = False
    if request.method == 'POST':
        if 'cancel' in request.POST:
            if username:
                return HttpResponseRedirect(reverse('member', args=[username]))
            else:
                return HttpResponseRedirect(reverse('members'))
        if 'delete' in request.POST:
            member.delete()
            user.delete()
            return HttpResponseRedirect(reverse('members'))
        user_form = forms.UserForm(request.POST, prefix='user', instance=user)
        member_form = forms.MemberForm(request.POST, prefix='member', 
                instance=member)
        related_account_formset = forms.RelatedAccountFormSet(request.POST, 
                instance=member, prefix='related_account')
        address_formset = forms.AddressFormSet(request.POST, instance=member,
                prefix='address')
        email_formset = forms.EmailFormSet(request.POST, instance=member,
                prefix='email')
        phone_formset = forms.PhoneFormSet(request.POST, instance=member,
                prefix='phone')
        LOA_formset = forms.LeaveOfAbsenceFormSet(request.POST, 
                instance=member, prefix='leave_of_absence')
        if (user_form.is_valid() and member_form.is_valid() and 
                related_account_formset.is_valid() and 
                address_formset.is_valid() and phone_formset.is_valid() 
                and email_formset.is_valid() and LOA_formset.is_valid()):
            user = user_form.save()
            member = member_form.save(commit=False)
            member.user = user
            member.save()
            for formset in (related_account_formset, LOA_formset, 
                    address_formset, email_formset, phone_formset):
                _setattr_formset_save(formset, 'member', member)
            return HttpResponseRedirect(reverse('member', args=[user.username]))
        else:
            is_errors = True
    else:
        user_form = forms.UserForm(instance=user, prefix='user')
        member_form = forms.MemberForm(instance=member, prefix='member')
        related_account_formset = forms.RelatedAccountFormSet(instance=member, 
                prefix='related_account')
        address_formset = forms.AddressFormSet(instance=member, 
                prefix='address')
        email_formset = forms.EmailFormSet(instance=member, prefix='email')
        phone_formset = forms.PhoneFormSet(instance=member, prefix='phone')
        LOA_formset = forms.LeaveOfAbsenceFormSet(instance=member, 
                prefix='leave_of_absence')
    context = RequestContext(request)
    context['member'] = member
    context['user_form'] = user_form
    context['member_form'] = member_form
    context['formsets'] = [
        (related_account_formset, 'Accounts'), 
        (LOA_formset, 'Leaves of Absence'),
        (address_formset, 'Addresses'), 
        (email_formset, 'Email Addresses'),
        (phone_formset, 'Phones'),
    ]
    context['is_errors'] = is_errors
    context['edit'] = bool(username)
    template = get_template('membership/member_form.html')
    return HttpResponse(template.render(context))

@user_passes_test(lambda u: u.is_authenticated())
def accounts(request):
    '''
    list of accounts
    '''
    context = RequestContext(request)
    if not request.user.is_staff:
        member = models.Member.objects.get(user=request.user)
        accounts = member.accounts.all()
    else:
        accounts = models.Account.objects.all()
        if not 'sort_by' in request.GET:
            form = forms.AccountListFilterForm()
            accounts = accounts.filter(members__date_missing__isnull=True, 
                    members__date_departed__isnull=True).distinct()
        else: 
            form = forms.AccountListFilterForm(request.GET)
            if form.is_valid():
                search = form.cleaned_data.get('search')
                if search:
                    accounts = accounts.filter(
                            Q(name__icontains=search) |
                            Q(note__icontains=search))
                sort = form.cleaned_data['sort_by']
                if sort == 'alpha':
                    accounts = accounts.order_by('name')
                elif sort == 'recent':
                    accounts = accounts.order_by('-id')
                elif sort == 'hours':
                    accounts = accounts.order_by('-hours_balance')
                elif sort == 'balance':
                    accounts = accounts.order_by('-balance')
                if not form.cleaned_data['active']:
                    accounts = accounts.exclude(
                            members__date_missing__isnull=True, 
                            members__date_departed__isnull=True)
                if form.cleaned_data['inactive']:
                    context['inactive'] = True
                else:
                    accounts = accounts.filter(
                            members__date_missing__isnull=True, 
                            members__date_departed__isnull=True).distinct()
        context['form'] = form
    pager = p.Paginator(accounts, PER_PAGE)
    context['pager'] = pager
    page_number = request.GET.get('p')
    context['page'] = _get_current_page(pager, page_number)
    context['query_string'] = request.META['QUERY_STRING'].split('&p=', 1)[0]
    template = get_template('membership/accounts.html')
    return HttpResponse(template.render(context))

def daterange(start, end):
    while start < end:
        yield start
        start += datetime.timedelta(1)

def workhist(account):
    '''
    Generates the work history object used to produce the workhistory calendar on account page.
    complex data structures here:
    workhist[] is an array of weeks
    each week is a {} dictionary of {'days':[array], 'tasks':[array], 
       'newmonth' and 'newyear'} (newmonth and newyear flags show month 
       alongside the calendar)
    each day is a {} dictionary of {'week':(parent-pointer), 'date':(number),
       'workflag':(flag for highlighting), 'task':last-task}
    '''
    workhist = []
    dayindex = {}
    today = datetime.date.today()
    lastsunday = today - datetime.timedelta(days=today.weekday()+1)
    try:
        oldesttime = account.task_set.all().order_by('time')[0].time
        oldestweeks = ((today - oldesttime.date()).days / 7) + 2
        oldestweeks = max(oldestweeks, 16)
    except IndexError:
        oldestweeks = 16
    for weeksaway in range(-oldestweeks,52):
        week = {'tasks':[]}
        if weeksaway == -12:
            week['flagcurrent'] = True
        elif weeksaway == 7:
            week['flagfuture'] = True
        firstday = lastsunday + datetime.timedelta(days=7*weeksaway)
        week['days'] = [{'week':week} for i in range(7)]
        for i in range(7):
            week['days'][i]['date'] = firstday + datetime.timedelta(days=i)
            dayindex[week['days'][i]['date']] = week['days'][i]
        if 7 <= week['days'][6]['date'].day < 14:
            week['newmonth'] = week['days'][6]['date']
        elif 14 <= week['days'][6]['date'].day < 21:
            week['newyear'] = week['days'][6]['date'].year
        workhist.append(week)
    for task in account.task_set.all():
        if task.time.date() in dayindex:
            day = dayindex[task.time.date()]
            if 'workflag' in day:
                day['workflag'] = 'complex-workflag'
            else:
                day['workflag'] = task.simple_workflag
            day['task'] = task
            day['week']['tasks'].append(task)
    for leave in models.LeaveOfAbsence.objects.filter(
                        member__accounts__id=account.id):
        for dayofleave in daterange(leave.start, leave.end):
            if dayofleave not in dayindex: 
                continue
            day = dayindex[dayofleave]
            if 'workflag' not in day:
                day['workflag'] = 'LOA'
    dayindex[today]['istoday'] = True
    return workhist        

@user_passes_test(lambda u: u.is_authenticated())
def account(request, id):
    '''
    individual account page
    '''
    account = get_object_or_404(models.Account, id=id)
    request_member = models.Member.objects.get(user=request.user)
    if not request.user.is_staff and not (request.user.is_authenticated() 
            and request_member in account.members.all()):
        return HttpResponseRedirect(reverse('login'))
    context = RequestContext(request)
    context['account'] = account
    transactions = account.transaction_set.all()
    context['transactions'] = transactions
    context['workhist'] = workhist(account)
    template = get_template('membership/account.html')
    return HttpResponse(template.render(context))

@user_passes_test(lambda u: u.is_staff)
def account_form(request, id=None):
    '''
    edit account info
    '''
    context = RequestContext(request)
    if id:
        account = get_object_or_404(models.Account, id=id)
        context['edit'] = True
    else:
        account = models.Account()
    if request.method == 'POST':
        if 'cancel' in request.POST:
            if id:
                return HttpResponseRedirect(reverse('account', args=[id]))
            else:
                return HttpResponseRedirect(reverse('accounts'))
        if 'delete' in request.POST:
            account.delete()
            return HttpResponseRedirect(reverse('accounts'))
        form = forms.AccountForm(request.POST, instance=account)
        related_member_formset = forms.RelatedMemberFormSet(request.POST, 
                instance=account, prefix='related_member')
        if form.is_valid() and related_member_formset.is_valid():
            account = form.save()
            _setattr_formset_save(related_member_formset, 'account', account)
            return HttpResponseRedirect(reverse('account', args=[account.id]))
    else:
        form = forms.AccountForm(instance=account)
        related_member_formset = forms.RelatedMemberFormSet(instance=account, 
                prefix='related_member')
    context['account'] = account
    context['form'] = form
    context['formsets'] = [
        (related_member_formset, 'Members'), 
    ]
    template = get_template('membership/account_form.html')
    return HttpResponse(template.render(context))

@user_passes_test(lambda u: u.is_authenticated())
def contact_form(request, username=None, medium=None, id=0):
    '''
    sub-page of member edit page.  ?
    '''
    context = RequestContext(request)
    referer = request.META.get('HTTP_REFERER', '')
    user = get_object_or_404(User, username=username)
    # medium may be 'address', 'phone', or 'email'
    MediumForm = forms.__getattribute__(medium.capitalize() + 'Form')
    MediumModel = models.__getattribute__(medium.capitalize())
    if id:
        medium_obj = get_object_or_404(MediumModel, id=id)
    else:
        medium_obj = MediumModel()
        context['add'] = True
    if request.method == 'POST':
        if 'cancel' in request.POST:
            return HttpResponseRedirect(reverse('member', args=[username]))
        form = MediumForm(request.POST, instance=medium_obj)
        referer = request.POST.get('referer')
        if form.is_valid():
            instance = form.save(commit=False)
            instance.member = user.get_profile()
            instance.save()
            if referer:
                return HttpResponseRedirect(referer)
            else:
                return HttpResponseRedirect(reverse('member', args=[username]))
    else:
        form = MediumForm(instance=medium_obj)
    context['form'] = form
    context['medium'] = medium
    context['referer'] = referer
    # use 'this_user' because context['user'] overrides logged-in user 
    context['this_user'] = user
    return render_to_response('membership/contact_form.html', context)

@user_passes_test(lambda u: u.is_authenticated())
def remove_contact(request, username=None, medium=None, id=None):
    '''
    delete a piece of contact info.
    '''
    context = RequestContext(request)
    MediumModel = models.__getattribute__(medium.capitalize())
    medium_obj = get_object_or_404(MediumModel, id=id)
    if request.method == 'POST':
        if 'cancel' in request.POST:
            return HttpResponseRedirect(reverse('member', args=[username]))
        medium_obj.delete()
        return HttpResponseRedirect(reverse('member', args=[username]))
    user = get_object_or_404(User, username=username)
    context['this_user'] = user
    context['contact'] = medium_obj
    context['medium'] = medium
    template = get_template('membership/remove_contact.html')
    return HttpResponse(template.render(context))

@user_passes_test(lambda u: u.is_staff)
def depart_account(request, id):
    # anna is working on this.
    '''
    confirms departure of all members on account.  prompts today's date but editable.
    sets departure date and cancels all workshifts after said date.
    '''
    context = RequestContext(request)
    account = get_object_or_404(models.Account, id=id)
    if request.method == 'POST':   # user clicked one of the buttons
        if 'cancel' in request.POST:   # cancel button
            return HttpResponseRedirect(account.get_absolute_url())
        form = forms.DateForm(request.POST)
        if form.is_valid():            # save button
            for mem in account.members.all():
                if not mem.date_departed:
                    mem.date_departed = form.cleaned_data['day']
                    mem.save()
                # open future workshifts.  
                r_rule_switch = {}
                for task in mem.task_set.filter(time__gt=mem.date_departed):
                    task.member = None
                    task.account = None
                    # if the task had a recur rule, deal with it:
                    # copy the recur rule into a new rule and set until date departed on old rule.
                    # keep old tasks attached to the old rule.
                    # switch future tasks to new rule.
                    if task.recur_rule:
                        if task.recur_rule in r_rule_switch:
                            new_rule = r_rule_switch[task.recur_rule]
                        else:
                            new_rule = s_models.RecurRule(frequency=task.recur_rule.frequency, interval=task.recur_rule.interval, until=task.recur_rule.until)
                            new_rule.save()
                            task.recur_rule.until = mem.date_departed
                            task.recur_rule.save()
                            r_rule_switch[task.recur_rule]=new_rule
                        task.recur_rule=new_rule
                    task.save()
                    # if it ahs a recur rule, check whether the recur rule is
                    # in our dictionary.  if it's in there
                    # if it has no recur rule, unset its member and account
                    # else append 
            return HttpResponseRedirect(account.get_absolute_url())
    else:                         # show prompt with default form values.
        form = forms.DateForm()
    context['account']=account
    context['form'] = form
    return render_to_response('membership/depart.html', context)


def formset_form(request, medium):
    context = RequestContext(request)
    form_name = ''.join([x.capitalize() for x in medium.split('_')]) + 'Form'
    MediumForm = forms.__getattribute__(form_name)
    index = request.GET.get('index')
    if index:
        form = MediumForm(prefix='%s-%s' % (medium, index))
    else:
        form = MediumForm()
    context['form'] = form
    template = get_template('membership/snippets/formset_form.html')
    return HttpResponse(template.render(context))


@user_passes_test(lambda u: u.is_staff)
def accountmemberflags(request):
    ''' show and allow editing of accountmember flags 
        (contact aka deposit holder; shopper).  
        this is kind of a report, but allows editing of the flags... '''
    results = []
    am = models.AccountMember.objects.all().order_by('-id')
    if request.method == 'POST':
        amformset = forms.AccountMemberFlagsFormSet(request.POST, queryset=am)
        if amformset.is_valid():
            amformset.save()
            results.append('Formset was valid and saved...')
        else:
            results.append('Formset was invalid...')
            results.append(amformset.errors)
    else:
        amformset = forms.AccountMemberFlagsFormSet(queryset=am)
    # loop to mark each new account
    curracct = None
    for form in amformset.forms[::-1]:
        form.diffacct = (form.instance.account != curracct)
        form.anomaly = (form.instance.account_contact == form.instance.shopper)
        curracct = form.instance.account
    return render_to_response('membership/accountmemberflags.html', locals(),
            context_instance=RequestContext(request))

# helper functions below

def _setattr_formset_save(formset, name, value):
    instances = formset.save(commit=False)
    for instance in instances:
        setattr(instance, name, value)
        instance.save()

def _get_current_page(pager, page_number):
    try:
        current_page = pager.page(page_number)
    except (p.PageNotAnInteger, TypeError):
        current_page = pager.page(1)
    return current_page

# merged with member_edit into member_form
#@user_passes_test(lambda u: u.is_staff)
#def member_add(request):
#    if not request.user.is_staff:
#        return HttpResponseRedirect(reverse('login'))
#    is_errors = False
#    # a fake member (no member should have an id of 0) will return
#    # no addresses, phones, or emails
#    member = models.Member()
#    if request.method == 'POST':
#        if 'cancel' in request.POST:
#            return HttpResponseRedirect(reverse('member', args=[username]))
#        user_form = forms.UserForm(request.POST, prefix='user')
#        member_form = forms.MemberForm(request.POST, prefix='member')
#        #related_accounts_form = forms.RelatedAccountsForm(member, 
#        #        request.POST, prefix='related')
#        address_formset = forms.AddressFormSet(request.POST, instance=member, prefix='address',
#                queryset=member.addresses.all())
#        email_formset = forms.EmailFormSet(request.POST, prefix='email',
#                queryset=member.emails.all())
#        phone_formset = forms.PhoneFormSet(request.POST, prefix='phone',
#                queryset=member.phones.all())
#        if (user_form.is_valid() and member_form.is_valid() and 
#                #related_accounts_form.is_valid() and 
#                address_formset.is_valid() and phone_formset.is_valid() 
#                and email_formset.is_valid()):
#            # need to do password business
#            # email member with temp password?
#            user = user_form.save()
#            member = models.Member(**member_form.cleaned_data)
#            member.user = user
#            member.save()
#            #related_accounts = related_accounts_form.cleaned_data['accounts']
#            member.accounts = related_accounts
#            member.save()
#            for formset in (address_formset, email_formset, phone_formset):
#                _new_member_formset_save(member, formset)
#            return HttpResponseRedirect(reverse('member', 
#                    args=[member.user.username]))
#        else:
#            is_errors = True
#    else:
#        user_form = forms.UserForm(prefix='user')
#        member_form = forms.MemberForm(prefix='member')
#        #related_accounts_form = forms.RelatedAccountsForm(member, 
#        #        prefix='related')
#        address_formset = forms.AddressFormSet(instance=member, 
#                prefix='address')
#        email_formset = forms.EmailFormSet(instance=member, prefix='email')
#        phone_formset = forms.PhoneFormSet(instance=member, prefix='phone')
#    context = RequestContext(request)
#    context['user_form'] = user_form
#    context['member_form'] = member_form
#    #context['related_accounts_form'] = related_accounts_form
#    context['formsets'] = [
#        (address_formset, 'Addresses'), 
#        (email_formset, 'Email Addresses'),
#        (phone_formset, 'Phones'),
#    ]
#    context['is_errors'] = is_errors
#    context['add'] = True
#    template = get_template('membership/member_form.html')
#    return HttpResponse(template.render(context))

# not needed now that contacts aren't many-to-many
#def fancy_save(formset):
#    object_list = []
#    for form in formset.forms:
#        if form.cleaned_data.get('DELETE') or not form.cleaned_data:
#            continue
#        field_dict = {}
#        for key in form.cleaned_data:
#            if key not in ('DELETE', 'id'):
#                field_dict[key] = form.cleaned_data[key]
#        try:
#            match = formset.model.objects.get(**field_dict)
#        except formset.model.DoesNotExist:
#            match = None
#        if match:
#            object_list.append(match)
#        else:
#            instance = formset.model()
#            for key in form.cleaned_data:
#                if key != 'id':
#                    instance.__dict__[key] = form.cleaned_data[key]
#            instance.save()
#            object_list.append(instance)
#    return object_list

# This raw_list function outputs raw data for use by ajax and xmlhttprequest.
# Since the data is output raw, it doesn't use any template.
#def raw_list(request):
#	# try.  Catches non-integers, blank field, and missing field
#	try: maxresults = int(request.GET.get('maxresults'))
#	except: maxresults = 30
#
#	# if we're listing accounts, list accounts matching pattern.
#	# don't bother checking the location of *'s, assume account=*pattern*
#	if request.GET.has_key('list') and request.GET.get('list') == 'accounts':
#		account_list = models.Account.objects.all()
#		if request.GET.has_key('account'):
#			pattern = request.GET.get('account').replace('*','')
#			account_list = account_list.filter(name__contains = pattern)
#		account_names = account_list.values_list('name',flat=True)[:maxresults]
#		return HttpResponse('\n'.join(account_names))
#
#	# if we're listing members, list members matching account and/or pattern
#	# note: This part may be SLOW due to [python-iteration] over all db entries
#	if request.GET.has_key('list') and request.GET.get('list') == 'members':
#		if request.GET.has_key('account'):
#			acct = request.GET.get('account')
#			member_list = models.Member.objects.filter(accounts__name = acct)
#		else:
#			member_list = models.Member.objects.all()
#		mnames = [member.user.get_full_name() for member in member_list]
#
#		# if we have a member pattern, filter it case-insensitively
## CAN'T SEEM TO DO A DATABASE FILTER ON member__user__get_full_name__contains
#		if request.GET.has_key('member'):
#			pattern = request.GET.get('member').replace('*','').lower()
#			mnames = [m for m in mnames if m.lower().find(pattern) >= 0]
#
#		mnames = mnames[:maxresults]
#		return HttpResponse('\n'.join(mnames))		
#
#	# if we're not sure what we're listing, fail
#	return HttpResponse('error in request for raw list')
