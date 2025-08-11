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
            #  Shipping fields
            'shipping_first_name', 'shipping_last_name', 'shipping_phone', 'shipping_email',
            'shipping_address_line_1', 'shipping_address_line_2', 'shipping_country',
            'shipping_state', 'shipping_city', 'shipping_zip_code',
        ]

    # Override country to use dropdown with choices, preset to US
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        initial='US',
        label='Country',
        help_text='Select your country (US only at this time)'
    )

    # Override shipping_country to use dropdown with choices, preset to US, optional
    shipping_country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        initial='US',
        label='Shipping Country',
        required=False,  # Optional; can fallback to billing country
        help_text='Select shipping country (defaults to billing if blank)'
    )

 # NEW: Clean and capitalize billing city
    def clean_city(self):
        city = self.cleaned_data.get('city')
        if city:
            return city.title()  # Capitalizes first letter of each word (e.g., "new york" -> "New York")
        return city  # If blank, leave as is

    # NEW: Clean and capitalize shipping city
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