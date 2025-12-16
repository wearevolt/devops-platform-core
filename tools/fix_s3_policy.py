#!/usr/bin/env python3
"""
Скрипт для исправления политики S3 бакета для SSO пользователей
"""

import boto3
import json
import sys

def get_current_user_arn():
    """Получить ARN текущего пользователя"""
    try:
        sts_client = boto3.client('sts')
        caller_identity = sts_client.get_caller_identity()
        return caller_identity["Arn"]
    except Exception as e:
        print(f"Ошибка при получении ARN пользователя: {e}")
        return None

def get_account_id():
    """Получить ID аккаунта"""
    try:
        sts_client = boto3.client('sts')
        caller_identity = sts_client.get_caller_identity()
        return caller_identity["Account"]
    except Exception as e:
        print(f"Ошибка при получении ID аккаунта: {e}")
        return None

def fix_s3_bucket_policy(bucket_name):
    """Исправить политику S3 бакета"""
    
    current_user_arn = get_current_user_arn()
    account_id = get_account_id()
    
    if not current_user_arn or not account_id:
        print("Не удалось получить ARN пользователя или ID аккаунта")
        return False
    
    # Для SSO пользователей добавляем дополнительные ARN для доступа через UI
    allowed_arns = [
        current_user_arn,
        f"arn:aws:iam::{account_id}:role/dev-platform-iac_pr_automation-role",
        f"arn:aws:iam::{account_id}:root",
        # Always allow AdministratorAccess SSO role (any session)
        f"arn:aws:sts::{account_id}:assumed-role/AWSReservedSSO_AdministratorAccess_*/*",
        f"arn:aws:iam::{account_id}:role/aws-reserved/sso.amazonaws.com/*/AWSReservedSSO_AdministratorAccess_*",
    ]
    
    # Если это SSO assumed role, добавляем базовый ARN роли без имени сессии
    if "assumed-role" in current_user_arn:
        # Извлекаем базовый ARN роли из assumed role ARN
        # arn:aws:sts::account:assumed-role/role-name/session-name
        # становится arn:aws:iam::account:role/role-name
        parts = current_user_arn.split(':')
        if len(parts) >= 6:
            account_id_from_arn = parts[4]
            role_parts = parts[5].split('/')
            if len(role_parts) >= 2:
                role_name = role_parts[1]  # Получаем имя роли без сессии
                base_role_arn = f"arn:aws:iam::{account_id_from_arn}:role/{role_name}"
                # Add wildcard pattern for any session of this role
                wildcard_arn = f"arn:aws:sts::{account_id_from_arn}:assumed-role/{role_name}/*"
                allowed_arns.append(base_role_arn)
                allowed_arns.append(wildcard_arn)
    
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            # non-restrictive allow-list
            {
                "Sid": "RestrictS3Access",
                "Action": ["s3:*"],
                "Effect": "Allow",
                "Principal": "*",
                "Condition": {
                    "ArnLike": {
                        "aws:PrincipalArn": allowed_arns
                    }
                },
                "Resource": [f"arn:aws:s3:::{bucket_name}", f"arn:aws:s3:::{bucket_name}/*"],
            },
            # an explicit deny. this one is self-sufficient
            {
                "Sid": "ExplicitlyDenyS3Actions",
                "Action": ["s3:*"],
                "Effect": "Deny",
                "Principal": "*",
                "Condition": {
                    "ArnNotLike": {
                        "aws:PrincipalArn": allowed_arns
                    }
                },
                "Resource": [f"arn:aws:s3:::{bucket_name}", f"arn:aws:s3:::{bucket_name}/*"],
            }
        ]
    }
    
    try:
        s3_client = boto3.client('s3')
        s3_client.put_bucket_policy(
            Bucket=bucket_name,
            Policy=json.dumps(bucket_policy)
        )
        print(f"Политика бакета {bucket_name} успешно обновлена")
        print("Разрешенные ARN:")
        for arn in allowed_arns:
            print(f"  - {arn}")
        return True
    except Exception as e:
        print(f"Ошибка при обновлении политики бакета: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python fix_s3_policy.py <bucket-name>")
        print("Пример: python fix_s3_policy.py wearevolt-gitops-kys71esk")
        sys.exit(1)
    
    bucket_name = sys.argv[1]
    print(f"Исправление политики для бакета: {bucket_name}")
    
    if fix_s3_bucket_policy(bucket_name):
        print("Политика успешно обновлена!")
    else:
        print("Ошибка при обновлении политики")
        sys.exit(1) 
