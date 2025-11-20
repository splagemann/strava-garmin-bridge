import { useState } from 'react';
import { useFilters } from '../hooks/useFilters';
import { toast } from 'sonner';
import { FILTER_TYPE_COLORS } from '../lib/constants';

export default function FiltersPage() {
  const { filters, createFilter, deleteFilter, updateFilter, isCreating } = useFilters();
  const [showForm, setShowForm] = useState(false);
  const [filterType, setFilterType] = useState<'include' | 'exclude'>('include');
  const [pattern, setPattern] = useState('');
  const [isRegex, setIsRegex] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createFilter({
        filter_type: filterType,
        pattern,
        is_regex: isRegex,
        active: true,
      });
      toast.success('Filter created successfully!');
      setPattern('');
      setShowForm(false);
    } catch (error) {
      toast.error('Failed to create filter');
    }
  };

  const handleDelete = async (id: number) => {
    if (confirm('Are you sure you want to delete this filter?')) {
      try {
        await deleteFilter(id);
        toast.success('Filter deleted');
      } catch (error) {
        toast.error('Failed to delete filter');
      }
    }
  };

  const toggleActive = async (id: number, active: boolean) => {
    try {
      await updateFilter(id, { active: !active });
      toast.success(`Filter ${!active ? 'activated' : 'deactivated'}`);
    } catch (error) {
      toast.error('Failed to update filter');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Activity Filters</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-primary hover:bg-primary/90 text-white px-4 py-2 rounded-md font-medium"
        >
          {showForm ? 'Cancel' : 'New Filter'}
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Create Filter</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Filter Type</label>
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value as 'include' | 'exclude')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="include">Include</option>
                <option value="exclude">Exclude</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Pattern</label>
              <input
                type="text"
                value={pattern}
                onChange={(e) => setPattern(e.target.value)}
                required
                placeholder="e.g., Morning Run"
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
            <div className="flex items-center">
              <input
                type="checkbox"
                id="regex"
                checked={isRegex}
                onChange={(e) => setIsRegex(e.target.checked)}
                className="mr-2"
              />
              <label htmlFor="regex" className="text-sm text-gray-700">Use Regular Expression</label>
            </div>
            <button
              type="submit"
              disabled={isCreating}
              className="w-full bg-primary hover:bg-primary/90 text-white py-2 rounded-md font-medium disabled:opacity-50"
            >
              {isCreating ? 'Creating...' : 'Create Filter'}
            </button>
          </form>
        </div>
      )}

      <div className="bg-white rounded-lg shadow divide-y">
        {filters.map((filter) => (
          <div key={filter.id} className="px-6 py-4 flex items-center justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <span className={`px-3 py-1 rounded-full text-xs font-medium border ${FILTER_TYPE_COLORS[filter.filter_type]}`}>
                  {filter.filter_type}
                </span>
                <span className="font-medium">{filter.pattern}</span>
                {filter.is_regex && <span className="text-xs text-gray-500">(regex)</span>}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => toggleActive(filter.id, filter.active)}
                className={`px-3 py-1 rounded-md text-sm font-medium ${
                  filter.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
                }`}
              >
                {filter.active ? 'Active' : 'Inactive'}
              </button>
              <button
                onClick={() => handleDelete(filter.id)}
                className="text-red-600 hover:text-red-800 text-sm font-medium"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
        {filters.length === 0 && (
          <div className="px-6 py-12 text-center text-gray-500">
            No filters yet. Create one to get started!
          </div>
        )}
      </div>
    </div>
  );
}
