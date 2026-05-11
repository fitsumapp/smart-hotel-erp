from django import forms
from .models import Hotel, PACKAGE_CHOICES
from users.models import User
from django.contrib.auth.hashers import make_password
import re

class HotelAdminForm(forms.ModelForm):
    admin_email = forms.EmailField(
        required=True,
        help_text="Primary email for the hotel's admin dashboard.",
    )
    admin_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        help_text="Set a new password. If editing, leave blank to keep unchanged.",
    )
    schema_name = forms.CharField(
        required=False,
        help_text="Auto-generated from hotel name if left blank.",
    )
    enabled_features = forms.MultipleChoiceField(
        choices=PACKAGE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select the modules/packages to enable for this hotel.",
    )

    class Meta:
        model = Hotel
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # If editing, fetch the current admin email
            admin_user = User.objects.filter(tenant_schema=self.instance.schema_name, role="admin").first()
            if admin_user:
                self.fields['admin_email'].initial = admin_user.email
            
            # Make schema_name read-only and password optional
            if 'schema_name' in self.fields:
                self.fields['schema_name'].disabled = True
        else:
            self.fields['admin_password'].required = True

    def clean_schema_name(self):
        schema = self.cleaned_data.get("schema_name")
        if not schema and not self.instance.pk:
            name = self.cleaned_data.get("name", "new_hotel")
            schema = re.sub(r'[^a-z0-9]', '', name.lower())
            
            # Ensure uniqueness
            base_schema = schema
            counter = 1
            while Hotel.objects.filter(schema_name=schema).exists():
                schema = f"{base_schema}{counter}"
                counter += 1
                
        return schema
