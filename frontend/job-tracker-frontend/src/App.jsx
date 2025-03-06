import { useState, useEffect } from "react";
import axios from "axios";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBriefcase } from "@fortawesome/free-solid-svg-icons";

function App() {
  const [jobs, setJobs] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    const API_URL = import.meta.env.VITE_BACKEND_URL;
    axios
      .get(`${API_URL}/jobs/`)
      .then((response) => setJobs(response.data))
      .catch((error) => console.error("Error fetching jobs:", error));
  }, []);

  const filteredJobs = jobs.filter(job => {
    const company = job.company?.toLowerCase() || '';
    const jobTitle = job.job_title?.toLowerCase() || '';
    return (
      company.includes(searchTerm.toLowerCase()) ||
      jobTitle.includes(searchTerm.toLowerCase())
    );
  });

  const getStatusColor = (status) => {
    const statusColors = {
      applied: "bg-blue-500",
      interview: "bg-green-500",
      offer: "bg-yellow-500",
      rejected: "bg-red-500"
    };
    return statusColors[status.toLowerCase()] || "bg-gray-500";
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 text-gray-100">
      <header className="px-4 py-8 bg-gray-900/80 backdrop-blur-sm border-b border-gray-700">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent mb-8">
            Job Application Tracker
          </h1>
          
          <div className="flex flex-wrap gap-4 mb-8">
            <div className="flex-1 min-w-[200px] bg-gray-800/50 p-4 rounded-xl backdrop-blur-sm border border-gray-700">
              <div className="text-2xl font-bold text-purple-400">{jobs.length}</div>
              <div className="text-sm text-gray-400">Total Applications</div>
            </div>
            <div className="flex-1 min-w-[200px] bg-gray-800/50 p-4 rounded-xl backdrop-blur-sm border border-gray-700">
              <div className="text-2xl font-bold text-green-400">
                {jobs.filter(job => job.status === 'interview').length}
              </div>
              <div className="text-sm text-gray-400">Interviews</div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="mb-8">
          <input
            type="text"
            placeholder="Search jobs..."
            className="w-full p-4 bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredJobs.length === 0 ? (
            <div className="col-span-full text-center py-12 text-gray-400">
              <FontAwesomeIcon icon={faBriefcase} className="text-4xl mb-4" />
              <p>No job applications found</p>
            </div>
          ) : (
            filteredJobs.map((job) => (
              <div 
                key={job.id}
                className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-4 border border-gray-700 hover:border-purple-500 transition-all duration-200"
              >
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-lg font-semibold text-purple-400">{job.company}</h3>
                  <span className="text-sm text-gray-400">
                    {new Date(job.applied_date).toLocaleDateString()}
                  </span>
                </div>
                <h4 className="text-gray-200 font-medium mb-4">{job.job_title}</h4>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className={`${getStatusColor(job.status)} text-xs px-3 py-1 rounded-full`}>
                    {job.status}
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {job.tech_stack?.map((tech, index) => (
                      <span 
                        key={index}
                        className="text-xs px-2 py-1 bg-purple-500/10 text-purple-400 rounded-full"
                      >
                        {tech}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}

export default App;