from django import forms
from .models import Order

# Define country choices: (code, display_name). Limited to US for now; expand as needed.
COUNTRY_CHOICES = [
    ('US', 'United States'),
    # Add more later, e.g., ('CA', 'Canada'), ('GB', 'United Kingdom')
]
# State choices for lower 48 (abbrev, full_name)
STATE_CHOICES = [
    ('AL', 'Alabama'),
    ('AZ', 'Arizona'),
    ('AR', 'Arkansas'),
    ('CA', 'California'),
    ('CO', 'Colorado'),
    ('CT', 'Connecticut'),
    ('DE', 'Delaware'),
    ('FL', 'Florida'),
    ('GA', 'Georgia'),
    ('ID', 'Idaho'),
    ('IL', 'Illinois'),
    ('IN', 'Indiana'),
    ('IA', 'Iowa'),
    ('KS', 'Kansas'),
    ('KY', 'Kentucky'),
    ('LA', 'Louisiana'),
    ('ME', 'Maine'),
    ('MD', 'Maryland'),
    ('MA', 'Massachusetts'),
    ('MI', 'Michigan'),
    ('MN', 'Minnesota'),
    ('MS', 'Mississippi'),
    ('MO', 'Missouri'),
    ('MT', 'Montana'),
    ('NE', 'Nebraska'),
    ('NV', 'Nevada'),
    ('NH', 'New Hampshire'),
    ('NJ', 'New Jersey'),
    ('NM', 'New Mexico'),
    ('NY', 'New York'),
    ('NC', 'North Carolina'),
    ('ND', 'North Dakota'),
    ('OH', 'Ohio'),
    ('OK', 'Oklahoma'),
    ('OR', 'Oregon'),
    ('PA', 'Pennsylvania'),
    ('RI', 'Rhode Island'),
    ('SC', 'South Carolina'),
    ('SD', 'South Dakota'),
    ('TN', 'Tennessee'),
    ('TX', 'Texas'),
    ('UT', 'Utah'),
    ('VT', 'Vermont'),
    ('VA', 'Virginia'),
    ('WA', 'Washington'),
    ('WV', 'West Virginia'),
    ('WI', 'Wisconsin'),
    ('WY', 'Wyoming'),
]

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'first_name', 'last_name', 'phone', 'email', 'address_line_1',
            'address_line_2', 'city', 'state', 'country',
            'zip_code', 'order_note',
            'shipping_first_name', 'shipping_last_name', 'shipping_phone', 'shipping_email',
            'shipping_address_line_1', 'shipping_address_line_2', 'shipping_city', 'shipping_state',
            'shipping_country', 'shipping_zip_code',
        ]
        widgets = {
           # 'first_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            #'last_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
           # 'email': forms.EmailInput(attrs={'class': 'form-control', 'required': True}),
           # 'phone': forms.TextInput(attrs={'class': 'form-control', 'required': True, 'maxlength': '12'}),
            'address_line_1': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'address_line_2': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'state': forms.Select(attrs={'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-control'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'order_note': forms.Textarea(attrs={'class': 'form-control', 'rows': '2'}),
            'shipping_first_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'shipping_last_name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
           # 'shipping_email': forms.EmailInput(attrs={'class': 'form-control', 'required': True}),
          #  'shipping_phone': forms.TextInput(attrs={'class': 'form-control', 'required': True, 'maxlength': '12'}),
            'shipping_address_line_1': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'shipping_address_line_2': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_city': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'shipping_state': forms.Select(attrs={'class': 'form-control'}),
            'shipping_country': forms.Select(attrs={'class': 'form-control'}),
            'shipping_zip_code': forms.TextInput(attrs={'class': 'form-control', 'required': True}),

            # ... your existing ...
            'first_name': forms.TextInput(
                attrs={'class': 'form-control', 'required': True, 'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(
                attrs={'class': 'form-control', 'required': True, 'autocomplete': 'family-name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'required': True, 'autocomplete': 'email'}),
            'phone': forms.TextInput(
                attrs={'class': 'form-control', 'required': True, 'maxlength': '12', 'autocomplete': 'tel'}),
            'shipping_email': forms.EmailInput(
                attrs={'class': 'form-control', 'required': True, 'autocomplete': 'email'}),
            'shipping_phone': forms.TextInput(
                attrs={'class': 'form-control', 'required': True, 'maxlength': '12', 'autocomplete': 'tel'}),
            # Add for other fields if needed, e.g., 'zip_code': ... 'autocomplete': 'postal-code'
        }

    state = forms.ChoiceField(
        choices=[('', 'Select State')] + STATE_CHOICES,
        label="State",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    shipping_state = forms.ChoiceField(
        choices=[('', 'Select State')] + STATE_CHOICES,
        label="Shipping State",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        initial='US',
        label='Country',
        help_text='Select your country (US only at this time)',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    shipping_country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        initial='US',
        label='Shipping Country',
        required=False,
        help_text='Select shipping country (defaults to billing if blank)',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Assign STATE_CHOICES to state fields
        state_choices = [('', 'Select State')] + STATE_CHOICES
        self.fields['state'].choices = state_choices
        self.fields['shipping_state'].choices = state_choices
        # Assign COUNTRY_CHOICES
        self.fields['country'].choices = COUNTRY_CHOICES
        self.fields['shipping_country'].choices = COUNTRY_CHOICES
        # Override labels to match HTML
        self.fields['first_name'].label = "First Name"
        self.fields['last_name'].label = "Last Name"
        self.fields['phone'].label = "Phone Number"
        self.fields['email'].label = "Email"
        self.fields['address_line_1'].label = "Address Line 1"
        self.fields['address_line_2'].label = "Address Line 2"
        self.fields['city'].label = "City"
        self.fields['state'].label = "State"
        self.fields['country'].label = "Country"
        self.fields['zip_code'].label = "Zip Code"
        self.fields['order_note'].label = "Order Note"
        self.fields['shipping_first_name'].label = "First Name"
        self.fields['shipping_last_name'].label = "Last Name"
        self.fields['shipping_phone'].label = "Phone Number"
        self.fields['shipping_email'].label = "Email"
        self.fields['shipping_address_line_1'].label = "Address Line 1"
        self.fields['shipping_address_line_2'].label = "Address Line 2"
        self.fields['shipping_city'].label = "City"
        self.fields['shipping_state'].label = "State"
        self.fields['shipping_country'].label = "Country"
        self.fields['shipping_zip_code'].label = "Zip Code"

 #  Clean and capitalize billing city
    def clean_city(self):
        city = self.cleaned_data.get('city')
        if city:
            return city.title()  # Capitalizes first letter of each word (e.g., "new york" -> "New York")
        return city  # If blank, leave as is

    #  Clean and capitalize shipping city
    def clean_shipping_city(self):
        shipping_city = self.cleaned_data.get('shipping_city')
        if shipping_city:
            return shipping_city.title()
        return shipping_city

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            digits = ''.join(filter(str.isdigit, phone))  # Strip non-digits
            if len(digits) == 10:
                return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        return phone

    def clean_shipping_phone(self):
        shipping_phone = self.cleaned_data.get('shipping_phone')
        if shipping_phone:
            digits = ''.join(filter(str.isdigit, shipping_phone))
            if len(digits) == 10:
                return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        return shipping_phone