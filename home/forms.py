from django import forms

from .models import Comment, CommentSectionModel, Reply
from .validators import (
    validate_comment_name,
    validate_comment_text,
    validate_phone_number,
    validate_reply_text,
    validate_series_comment_text,
)


class CommentForm(forms.ModelForm):
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input enterprise-input contact-phone-input',
            'placeholder': 'شماره تماس',
            'inputmode': 'tel',
            'autocomplete': 'tel',
            'dir': 'ltr',
        }),
    )

    class Meta:
        model = Comment
        fields = ['comment', 'name', 'email', 'phone']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-textarea enterprise-input enterprise-textarea',
                'placeholder': 'پیام خود را با جزئیات کافی بنویسید',
                'rows': 6,
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-input enterprise-input',
                'placeholder': 'نام و نام خانوادگی',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input enterprise-input',
                'placeholder': 'ایمیل',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input enterprise-input',
                'placeholder': 'شماره تماس',
            }),
        }

    def clean_name(self):
        return validate_comment_name(self.cleaned_data.get('name'))

    def clean_comment(self):
        return validate_comment_text(self.cleaned_data.get('comment'))

    def clean_phone(self):
        return validate_phone_number(self.cleaned_data.get('phone'))


class CommentSectionForm(forms.ModelForm):
    class Meta:
        model = CommentSectionModel
        fields = ('text',)
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-textarea enterprise-input enterprise-textarea',
                'placeholder': 'دیدگاه یا پرسش خود را دقیق و شفاف بنویسید',
                'rows': 5,
            }),
        }
        labels = {'text': ''}

    def clean_text(self):
        return validate_series_comment_text(self.cleaned_data.get('text'))


class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ('text',)
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-textarea enterprise-input enterprise-textarea',
                'placeholder': 'پاسخ خود را بنویسید...',
                'rows': 3,
            }),
        }
        labels = {'text': ''}

    def clean_text(self):
        return validate_reply_text(self.cleaned_data.get('text'))
