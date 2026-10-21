"""Never grant anonymous object access while initializing application storage."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from minio.error import S3Error
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from services.storage_service import StorageService


class StoragePolicyTests(unittest.TestCase):
    def run_init(self, policy=None):
        storage = MagicMock()
        storage.client.bucket_exists.return_value = True
        if policy is None:
            storage.client.get_bucket_policy.side_effect = S3Error('NoSuchBucketPolicy','not set',None,'request','host',None)
        else:
            storage.client.get_bucket_policy.return_value = json.dumps(policy)
        with patch('services.storage_service.MinioStorage',return_value=storage), patch('services.storage_service.LocalStorage'):
            StorageService()
        storage.client.set_bucket_policy.assert_not_called()
        return storage.client

    def test_new_installation_keeps_private_bucket(self):
        self.run_init().delete_bucket_policy.assert_not_called()

    def test_only_legacy_anonymous_policy_is_removed(self):
        policy = {'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'AWS':['*']},'Action':['s3:GetObject'],'Resource':['arn:aws:s3:::orthophotos/*']}]}
        with patch('services.storage_service.config.MINIO_ORTHO_BUCKET','orthophotos'):
            self.run_init(policy).delete_bucket_policy.assert_called_once_with('orthophotos')

    def test_admin_managed_storage_policy_is_preserved(self):
        self.run_init({'Version':'2012-10-17','Statement':[]}).delete_bucket_policy.assert_not_called()
