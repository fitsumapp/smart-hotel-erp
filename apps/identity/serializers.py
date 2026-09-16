"""Identity serializers."""
from users.serializers import *  # noqa: F401,F403
from django.contrib.auth.password_validation import validate_password

class PublicRegistrationSerializer(serializers.ModelSerializer):
    """Accept only fields that an untrusted public registrant may set."""

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "phone_number", "password",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "password": {"write_only": True, "trim_whitespace": False},
        }

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value.strip()).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.strip().lower()

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.role = User.CUSTOMER
        user.is_active = False
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    """Administrative serializer for staff account management."""

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "role", "phone_number", "profile_picture", "is_active", "password",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "password": {
                "write_only": True,
                "required": False,
                "trim_whitespace": False,
            }
        }

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        is_active = validated_data.pop("is_active", False)
        user = User(**validated_data)
        user.is_active = is_active
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance


