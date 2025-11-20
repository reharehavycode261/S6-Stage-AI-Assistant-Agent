import { Card } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { PlayCircle } from 'lucide-react';

export function PlaygroundPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Playground</h1>
        <p className="text-gray-500 mt-1">Tester le workflow manuellement</p>
      </div>

      <Card title="Test du workflow">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Titre de la tâche</label>
            <input type="text" className="input w-full" placeholder="Ajouter une fonction login()" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
            <textarea className="input w-full h-32" placeholder="Description détaillée..." />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Repository URL</label>
            <input type="text" className="input w-full" placeholder="https://github.com/user/repo" />
          </div>

          <Button variant="primary">
            <PlayCircle className="h-4 w-4 mr-2" />
            Lancer le workflow
          </Button>
        </div>
      </Card>
    </div>
  );
}

