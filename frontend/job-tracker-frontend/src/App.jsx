import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [jobs, setJobs] = useState([]);

  // Fetch jobs from the FastAPI backend
  useEffect(() => {
    const API_URL = import.meta.env.VITE_BACKEND_URL;
    axios
      .get(`${API_URL}/jobs/`)
      .then((response) => setJobs(response.data))
      .catch((error) => console.error("Error fetching jobs:", error));
  }, []);

  return (
    <div className="app-container">
      <div className="content">
        <h1>Job Tracker</h1>
        <h2>Applied Jobs</h2>
        {jobs.length === 0 ? (
          <p>No job applications found.</p>
        ) : (
          <ul className="jobs-list">
            {jobs.map((job) => (
              <li key={job.id} className="job-card">
                <span className="job-company">{job.company}</span> -{" "}
                <span className="job-title">{job.job_title}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default App;
