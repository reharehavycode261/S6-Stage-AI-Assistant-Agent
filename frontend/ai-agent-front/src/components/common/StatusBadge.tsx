import { Badge } from './Badge';
import { formatStatus } from '@/utils/format';
import { WorkflowStatus, HumanValidationStatus } from '@/types';

interface StatusBadgeProps {
  status: WorkflowStatus | HumanValidationStatus | string;
  showDot?: boolean;
}

export function StatusBadge({ status, showDot = true }: StatusBadgeProps) {
  const getVariant = (status: string) => {
    if (status === 'completed' || status === 'approved') return 'success';
    if (status === 'failed' || status === 'rejected') return 'error';
    if (status === 'running') return 'info';
    if (status === 'pending') return 'warning';
    return 'default';
  };

  return (
    <Badge variant={getVariant(status)}>
      {showDot && (
        <span
          className={`status-dot ${
            status === 'running' ? 'status-dot-running' : ''
          } ${
            status === 'completed' || status === 'approved' ? 'status-dot-completed' : ''
          } ${
            status === 'failed' || status === 'rejected' ? 'status-dot-failed' : ''
          } ${
            status === 'pending' ? 'status-dot-pending' : ''
          } mr-1.5`}
        />
      )}
      {formatStatus(status)}
    </Badge>
  );
}

