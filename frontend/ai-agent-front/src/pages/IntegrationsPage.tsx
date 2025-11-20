import { Card } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Badge } from '@/components/common/Badge';
import { Check } from 'lucide-react';

export function IntegrationsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Intégrations</h1>
        <p className="text-gray-500 mt-1">Gestion des intégrations externes</p>
      </div>

      {/* Monday.com */}
      <Card title="Monday.com">
        <div className="flex items-center justify-between mb-4">
          <Badge variant="success">
            <Check className="h-3 w-3 mr-1" />
            Connecté
          </Badge>
          <Button variant="secondary" size="sm">Tester la connexion</Button>
        </div>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Board ID</span>
            <span className="font-medium">5084415062</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Items actifs</span>
            <span className="font-medium">42</span>
          </div>
        </div>
      </Card>

      {/* GitHub */}
      <Card title="GitHub">
        <div className="flex items-center justify-between mb-4">
          <Badge variant="success">
            <Check className="h-3 w-3 mr-1" />
            Connecté
          </Badge>
          <Button variant="secondary" size="sm">Tester la connexion</Button>
        </div>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Repositories</span>
            <span className="font-medium">12</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">PRs ouvertes</span>
            <span className="font-medium">5</span>
          </div>
        </div>
      </Card>

      {/* Slack */}
      <Card title="Slack">
        <div className="flex items-center justify-between mb-4">
          <Badge variant="success">
            <Check className="h-3 w-3 mr-1" />
            Connecté
          </Badge>
          <Button variant="secondary" size="sm">Tester la connexion</Button>
        </div>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Workspace</span>
            <span className="font-medium">VyCode Team</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Membres</span>
            <span className="font-medium">15</span>
          </div>
        </div>
      </Card>
    </div>
  );
}

