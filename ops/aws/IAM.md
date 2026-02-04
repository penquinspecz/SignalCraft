# IAM Roles for JobIntel (Runtime vs Operator)

This separates **runtime** permissions (pods publishing artifacts) from **operator** permissions (humans/CI verifying).
Do not widen runtime permissions just to make verification easier.

## Runtime (IRSA / ServiceAccount role)

Used by the Kubernetes CronJob pod to publish artifacts. Keep it minimal:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<bucket>",
      "Condition": {
        "StringLike": {
          "s3:prefix": [
            "<prefix>",
            "<prefix>/*"
          ]
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::<bucket>/<prefix>/*"
    }
  ]
}
```

## Operator (human/CI verify role)

Used by `scripts/verify_published_s3.py` and `scripts/prove_cloud_run.py` outside the cluster:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<bucket>",
      "Condition": {
        "StringLike": {
          "s3:prefix": [
            "<prefix>/runs/*",
            "<prefix>/latest/*"
          ]
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:HeadObject"
      ],
      "Resource": [
        "arn:aws:s3:::<bucket>/<prefix>/runs/*",
        "arn:aws:s3:::<bucket>/<prefix>/latest/*"
      ]
    }
  ]
}
```

## Why separate?

- Runtime pods only need to write artifacts; they should not need read access to all historical runs.
- Operator verification is a human/CI action with separate auditing and narrower usage.
