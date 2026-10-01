package boards

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
)

const (
	greenhouseAPIBaseURL = "https://boards-api.greenhouse.io/v1/boards"
	greenhouseUserAgent  = "job-radar/0.1 (personal job search)"
)

// This struct exists only to describe the shape of Greenhouse's
// reply, so Go knows how to unpack the JSON. Fields we don't
// care about can simply be left out.
type greenhouseResponse struct {
	Jobs []struct {
		ID          int64  `json:"id"`
		Title       string `json:"title"`
		AbsoluteURL string `json:"absolute_url"`
		UpdatedAt   string `json:"updated_at"`
		Content     string `json:"content"`
		Location    struct {
			Name string `json:"name"`
		} `json:"location"`
	} `json:"jobs"`
}

func FetchGreenhouse(ctx context.Context, c *http.Client, token string) ([]Job, error) {
	url := fmt.Sprintf("%s/%s/jobs?content=true", greenhouseAPIBaseURL, token)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	// Always identify your crawler. It is the polite thing to do
	// and it is what lets a site owner contact you instead of
	// silently blocking you.
	req.Header.Set("User-Agent", greenhouseUserAgent)

	resp, err := c.Do(req)
	if err != nil {
		return nil, err
	}
	// defer runs this when the function exits, however it exits.
	// Forgetting it leaks a connection every call.
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("greenhouse %s: status %d", token, resp.StatusCode)
	}

	var body greenhouseResponse
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return nil, fmt.Errorf("greenhouse %s: decode: %w", token, err)
	}

	jobs := make([]Job, 0, len(body.Jobs))
	for _, j := range body.Jobs {
		job := Job{
			Source:      "greenhouse",
			Company:     token,
			ExternalID:  fmt.Sprintf("%d", j.ID),
			Title:       j.Title,
			Location:    j.Location.Name,
			URL:         j.AbsoluteURL,
			Description: j.Content,
		}
		job.Hash = job.Fingerprint()
		jobs = append(jobs, job)
	}
	return jobs, nil
}
