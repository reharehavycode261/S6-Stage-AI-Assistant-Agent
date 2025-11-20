import { useState } from 'react';
import { Card } from '@/components/common/Card';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { StatusBadge } from '@/components/common/StatusBadge';
import ReactFlow, { Background, Controls, MiniMap, Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import { CheckCircle, XCircle, Clock, PlayCircle, RefreshCw } from 'lucide-react';
import { useActiveWorkflows, useRecentWorkflows, useWorkflow } from '@/hooks/useApi';

// Nodes du workflow LangGraph
const WORKFLOW_NODES = [
  'prepare',
  'analyze',
  'implement',
  'test',
  'QA',
  'finalize',
  'validation',
  'merge',
  'update',
];

export function WorkflowPage() {
  const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null);
  const { data: activeWorkflows, isLoading: loadingActive } = useActiveWorkflows();
  const { data: recentWorkflows, isLoading: loadingRecent } = useRecentWorkflows(5);
  
  // Utiliser le premier workflow actif ou le premier workflow récent
  const firstWorkflowId = (activeWorkflows as any)?.[0]?.workflow_id || (recentWorkflows as any)?.[0]?.workflow_id;
  const workflowToDisplay = selectedWorkflow || firstWorkflowId;
  
  const { data: workflowDataRaw, isLoading: loadingWorkflow } = useWorkflow(
    workflowToDisplay || '',
    { enabled: !!workflowToDisplay } as any
  );
  
  const workflowData = workflowDataRaw as any; // Type assertion
  const isLoading = loadingActive || loadingRecent || loadingWorkflow;

  if (isLoading && !workflowData) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!workflowData) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Workflow Visualization</h1>
          <p className="text-gray-500 mt-1">Visualisation du workflow LangGraph en temps réel</p>
        </div>
        <Card>
          <div className="text-center py-12 text-gray-500">
            <RefreshCw className="h-16 w-16 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">Aucun workflow disponible</p>
            <p className="text-sm mt-2">Les workflows apparaîtront ici quand ils seront exécutés</p>
          </div>
        </Card>
      </div>
    );
  }

  // Generate React Flow nodes depuis les données réelles
  const flowNodes: Node[] = WORKFLOW_NODES.map((node, index) => {
    const nodeData = workflowData?.nodes?.find((n: any) => n.id === node);
    const status = nodeData?.status || 'pending';
    
    let bgColor = '#f3f4f6'; // gray-100
    let borderColor = '#e5e7eb'; // gray-200
    let textColor = '#6b7280'; // gray-500

    if (status === 'completed') {
      bgColor = '#dcfce7'; // green-100
      borderColor = '#86efac'; // green-300
      textColor = '#166534'; // green-800
    } else if (status === 'running') {
      bgColor = '#dbeafe'; // blue-100
      borderColor = '#93c5fd'; // blue-300
      textColor = '#1e40af'; // blue-800
    } else if (status === 'failed') {
      bgColor = '#fee2e2'; // red-100
      borderColor = '#fca5a5'; // red-300
      textColor = '#991b1b'; // red-800
    }

    return {
      id: node,
      type: 'default',
      data: {
        label: (
          <div className="flex flex-col items-center gap-2 p-2">
            {status === 'completed' && <CheckCircle className="h-5 w-5 text-green-600" />}
            {status === 'running' && <PlayCircle className="h-5 w-5 text-blue-600 animate-pulse" />}
            {status === 'pending' && <Clock className="h-5 w-5 text-gray-400" />}
            {status === 'failed' && <XCircle className="h-5 w-5 text-red-600" />}
            <div style={{ color: textColor, fontWeight: 500 }}>{node}</div>
            {nodeData?.duration && (
              <div className="text-xs" style={{ color: textColor }}>
                {nodeData.duration}s
              </div>
            )}
          </div>
        ),
      },
      position: { x: 250, y: index * 120 },
      style: {
        backgroundColor: bgColor,
        border: `2px solid ${borderColor}`,
        borderRadius: '8px',
        padding: '8px',
        minWidth: '150px',
      },
    };
  });

  // Generate React Flow edges depuis les données réelles
  const flowEdges: Edge[] = WORKFLOW_NODES.slice(0, -1).map((node, index) => {
    const nodeData = workflowData.nodes.find((n: any) => n.id === node);
    return {
      id: `e${index}`,
      source: node,
      target: WORKFLOW_NODES[index + 1],
      animated: nodeData?.status === 'running',
      style: {
        stroke: nodeData?.status === 'completed' ? '#10b981' : '#9ca3af',
        strokeWidth: 2,
      },
    };
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Workflow Visualization</h1>
        <p className="text-gray-500 mt-1">Visualisation du workflow LangGraph en temps réel</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Workflow Graph */}
        <div className="lg:col-span-2">
          <Card title="Graphe du workflow">
            <div className="h-[800px]">
              <ReactFlow
                nodes={flowNodes}
                edges={flowEdges}
                fitView
                minZoom={0.5}
                maxZoom={1.5}
              >
                <Background />
                <Controls />
                <MiniMap />
              </ReactFlow>
            </div>
          </Card>
        </div>

        {/* Task Info & Node Details */}
        <div className="space-y-6">
          {/* Task Info - DONNÉES RÉELLES */}
          <Card title="Informations de la tâche">
            <div className="space-y-3">
              <div>
                <label className="text-sm text-gray-600">Titre</label>
                <p className="text-sm font-medium">{workflowData.title || 'N/A'}</p>
              </div>
              <div>
                <label className="text-sm text-gray-600">ID Monday.com</label>
                <p className="text-sm font-mono font-medium">{workflowData.task_id}</p>
              </div>
              <div>
                <label className="text-sm text-gray-600">Workflow ID</label>
                <p className="text-sm font-mono font-medium">{workflowData.workflow_id}</p>
              </div>
              <div>
                <label className="text-sm text-gray-600">Status</label>
                <StatusBadge status={workflowData.status} />
              </div>
              <div>
                <label className="text-sm text-gray-600">Nœud actuel</label>
                <p className="text-sm font-medium">{workflowData.current_node || 'N/A'}</p>
              </div>
              <div>
                <label className="text-sm text-gray-600">Progression</label>
                <div className="mt-2">
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all"
                      style={{ width: `${workflowData.progress_percentage}%` }}
                    />
                  </div>
                  <p className="text-sm text-gray-600 mt-1">
                    {workflowData.progress_percentage}% complete
                  </p>
                </div>
              </div>
            </div>
          </Card>

          {/* Node Details - DONNÉES RÉELLES */}
          <Card title="Détails des nœuds">
            <div className="space-y-2 max-h-[600px] overflow-y-auto scrollbar-thin">
              {workflowData.nodes.map((node: any) => (
                <div
                  key={node.id}
                  className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
                  onClick={() => setSelectedWorkflow(workflowData.workflow_id)}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{node.name}</span>
                    <StatusBadge status={node.status} />
                  </div>
                  {node.duration && (
                    <p className="text-xs text-gray-600">Durée: {node.duration}s</p>
                  )}
                  {node.error_details && (
                    <p className="text-xs text-red-600 mt-1">{node.error_details}</p>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

