import { useState, useEffect } from "react";
import axios from "axios";

function App() {
    const [jobs, setJobs] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        axios.get("http://127.0.0.1:8000/jobs/")
            .then(response => {
                setJobs(response.data);
                setIsLoading(false);
            })
            .catch(error => {
                console.error("Error fetching jobs:", error);
                setError("Failed to load jobs");
                setIsLoading(false);
            });
    }, []);

    const getStatusColor = (status) => {
        switch (status.toLowerCase()) {
            case 'applied': return 'bg-blue-100 text-blue-800';
            case 'interview': return 'bg-purple-100 text-purple-800';
            case 'offer': return 'bg-green-100 text-green-800';
            case 'rejected': return 'bg-red-100 text-red-800';
            default: return 'bg-gray-100 text-gray-800';
        }
    };

    return (
        <div className="min-h-screen bg-gray-50">
            <header className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 py-6">
                    <h1 className="text-3xl font-bold text-gray-900">Job Tracker</h1>
                    <p className="mt-2 text-gray-600">Your automated job application manager</p>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 py-8">
                {isLoading ? (
                    <div className="flex justify-center items-center h-64">
                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
                    </div>
                ) : error ? (
                    <div className="p-4 bg-red-50 text-red-700 rounded-lg">
                        {error}
                    </div>
                ) : (
                    <div className="bg-white rounded-lg shadow overflow-hidden">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <h2 className="text-xl font-semibold text-gray-800">
                                Applications ({jobs.length})
                            </h2>
                        </div>
                        {jobs.length === 0 ? (
                            <div className="p-12 text-center text-gray-500">
                                No job applications found in your inbox
                            </div>
                        ) : (
                            <ul className="divide-y divide-gray-200">
                                {jobs.map((job) => (
                                    <li key={job.id} className="px-6 py-4 hover:bg-gray-50 transition-colors">
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <div className="flex items-center space-x-2">
                                                    <h3 className="text-lg font-medium text-gray-900">
                                                        {job.company}
                                                    </h3>
                                                    {job.status && (
                                                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(job.status)}`}>
                                                            {job.status}
                                                        </span>
                                                    )}
                                                </div>
                                                <p className="mt-1 text-gray-600">{job.job_title}</p>
                                                {job.applied_date && (
                                                    <p className="mt-1 text-sm text-gray-500">
                                                        Applied on {new Date(job.applied_date).toLocaleDateString()}
                                                    </p>
                                                )}
                                            </div>
                                            <svg 
                                                className="h-5 w-5 text-gray-400" 
                                                fill="none" 
                                                stroke="currentColor" 
                                                viewBox="0 0 24 24"
                                            >
                                                <path 
                                                    strokeLinecap="round" 
                                                    strokeLinejoin="round" 
                                                    strokeWidth={2} 
                                                    d="M9 5l7 7-7 7" 
                                                />
                                            </svg>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                )}
            </main>

            <footer className="border-t border-gray-200 mt-12">
                <div className="max-w-7xl mx-auto px-4 py-8">
                    <p className="text-center text-gray-500 text-sm">
                        © 2023 Job Tracker. Automatically tracking your job applications.
                    </p>
                </div>
            </footer>
        </div>
    );
}

export default App;