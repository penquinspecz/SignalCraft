# M19B Success-Path IAM Unblock Log (2026-02-27)

Chronological log of least-privilege IAM unblocks on PR #236.

## Entry 1
- timestamp: `2026-02-27T04:05:24Z`
- execution_arn: `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T040524Z`
- failing_step: `BringupInfra`
- denied_action: `iam:ListRolePolicies`
- denied_resource: `arn:aws:iam::048622080012:role/jobintel-dr-runner-ssm-role`
- iam_change_made: `Action=[iam:ListRolePolicies] Resource=arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/jobintel-dr-runner-ssm-role`
- result_next_blocker: `Unblocked ListRolePolicies; next blocker became iam:ListAttachedRolePolicies on jobintel-dr-runner-ssm-role.`

## Entry 2
- timestamp: `2026-02-27T04:15:37Z`
- execution_arn: `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T041537Z`
- failing_step: `BringupInfra`
- denied_action: `iam:ListAttachedRolePolicies`
- denied_resource: `arn:aws:iam::048622080012:role/jobintel-dr-runner-ssm-role`
- iam_change_made: `Action=[iam:ListAttachedRolePolicies] Resource=arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/jobintel-dr-runner-ssm-role`
- result_next_blocker: `Unblocked ListAttachedRolePolicies; next blocker became iam:ListInstanceProfilesForRole on jobintel-dr-runner-ssm-role.`

## Entry 3
- timestamp: `2026-02-27T04:28:25Z`
- execution_arn: `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T042825Z`
- failing_step: `BringupInfra`
- denied_action: `iam:ListInstanceProfilesForRole`
- denied_resource: `arn:aws:iam::048622080012:role/jobintel-dr-runner-ssm-role`
- iam_change_made: `Action=[iam:ListInstanceProfilesForRole] Resource=arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/jobintel-dr-runner-ssm-role`
- result_next_blocker: `Unblocked ListInstanceProfilesForRole; next blocker became iam:TagInstanceProfile on jobintel-dr-runner-instance-profile.`

## Entry 4
- timestamp: `2026-02-27T04:44:03Z`
- execution_arn: `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T044403Z`
- failing_step: `BringupInfra`
- denied_action: `iam:TagInstanceProfile`
- denied_resource: `arn:aws:iam::048622080012:instance-profile/jobintel-dr-runner-instance-profile`
- iam_change_made: `Action=[iam:TagInstanceProfile] Resource=arn:aws:iam::${data.aws_caller_identity.current.account_id}:instance-profile/jobintel-dr-runner-instance-profile`
- result_next_blocker: `IAM blocker cleared; CodeBuild bringup SUCCEEDED. New blocker is non-IAM Step Functions runtime mapping error: missing $.receipt_bucket in BringupInfra output for States.Format('s3://{}/{}/{}/codebuild-bringup.json', ...).`

## Related proof docs
- `docs/proof/m19b-iam-listrolepolicies-fix-20260227T040524Z.md`
- `docs/proof/m19b-iam-listattachedrolepolicies-fix-20260227T041537Z.md`
- `docs/proof/m19b-iam-listinstanceprofilesforrole-fix-20260227T042825Z.md`
- `docs/proof/m19b-iam-taginstanceprofile-fix-20260227T044403Z.md`

## Entry 5
- timestamp: `2026-02-27T04:50:44Z`
- execution_arn: `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T045044Z`
- failing_step: `Validate`
- denied_action: `n/a (non-IAM)`
- denied_resource: `n/a`
- iam_change_made: `none`
- result_next_blocker: `Step Functions/validate path progressed past bringup and failed on shell portability: set: Illegal option -o pipefail in AWS-RunShellScript validate command.`

## Entry 6
- timestamp: `2026-02-27T05:00:57Z`
- execution_arn: `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T050057Z`
- failing_step: `Validate`
- denied_action: `n/a (non-IAM)`
- denied_resource: `n/a`
- iam_change_made: `none`
- result_next_blocker: `pipefail blocker cleared; Validate now fails because namespace jobintel is missing (k3s kubectl get ns jobintel returned NotFound).`

## Entry 7
- timestamp: `2026-02-27T05:07:07Z`
- execution_arn: `arn:aws:states:us-east-1:048622080012:execution:signalcraft-dr-orchestrator-state-machine:m19b-success-true-20260227T050707Z`
- failing_step: `n/a (no failure before manual gate)`
- denied_action: `n/a`
- denied_resource: `n/a`
- iam_change_made: `none`
- result_next_blocker: `Success-path reached RequestManualApproval (waitForTaskToken). Stop condition met; manual promote/record decision intentionally not executed in this rehearsal proof.`
