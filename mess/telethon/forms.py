import datetime

from django import forms
from mess.autocomplete import AutoCompleteWidget
from mess.telethon import models
from mess.membership import models as m_models

CRITERIA_CHOICES = (
    ('active', 'all active members'),
    ('pledges', 'pledges'),
    ('loans', 'loans / donations')
)

class JumpToMemberForm(forms.Form):
    member = forms.ModelChoiceField(m_models.Member.objects.all(),
        widget=AutoCompleteWidget('member_spiffy', attrs={'size':8}
            ,view_name='membership-autocomplete', canroundtrip=True),
        required=False, label='')
    
class SearchForm(forms.Form):
    search = forms.CharField(required=False)
    criteria = forms.ChoiceField(choices=CRITERIA_CHOICES)

class CallForm(forms.ModelForm):
    class Meta:
        model = models.Call
        exclude = ('callee','caller','loan')
