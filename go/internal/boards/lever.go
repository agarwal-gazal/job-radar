package boards

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
)

type leverPosting struct {
	ID               string `json:"id"`
	Text             string `json:"text"` // Lever calls the title "text"
	HostedURL        string `json:"hostedUrl"`
	DescriptionPlain string `json:"descriptionPlain"`
	Categories       struct {
		Location   string `json:"location"`
		Team       string `json:"team"`
		Commitment string `json:"commitment"`
	} `json:"categories"`
}

func FetchLever(ctx context.Context, c *http.Client, site string) ([]Job, error) {
	url := fmt.Sprintf("https://api.lever.co/v0/postings/%s?mode=json", site)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "job-radar/0.1 (personal job search)")

	resp, err := c.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("lever %s: status %d", site, resp.StatusCode)
	}

	// The top level is an array, so we decode into a slice.
	var postings []leverPosting
	if err := json.NewDecoder(resp.Body).Decode(&postings); err != nil {
		return nil, fmt.Errorf("lever %s: decode: %w", site, err)
	}

	jobs := make([]Job, 0, len(postings))
	for _, p := range postings {
		job := Job{
			Source:      "lever",
			Company:     site,
			ExternalID:  p.ID,
			Title:       p.Text,
			Location:    p.Categories.Location,
			URL:         p.HostedURL,
			Description: p.DescriptionPlain,
		}
		job.Hash = job.Fingerprint()
		jobs = append(jobs, job)
	}
	return jobs, nil
}
