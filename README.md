# Scrap-Sync: E-Waste Bidding Marketplace ♻️

Scrap-Sync is an AI-powered e-waste bidding marketplace built for a 48-hour hackathon. It allows users to upload images of their electronic waste, which are then analyzed using Anthropic's Claude 3 Haiku vision model (via AWS Bedrock) to automatically identify items and estimate their scrap value in INR. Once estimated, the lot is listed for recyclers to place their bids.

## 🚀 Features

- **AI-Powered Valuation:** Upload an image of e-waste, and Claude 3 Haiku automatically identifies the components and estimates their scrap market value.
- **Modern React Frontend:** A responsive, polished UI with drag-and-drop file uploading, error handling, and immediate analysis feedback.
- **Serverless Architecture:** Built entirely on AWS using API Gateway, Lambda, DynamoDB, and SNS for real-time alert notifications.
- **Local Hackathon Mode:** Includes a fully functional local API (`local_api.py`) that mimics the AWS API Gateway to bypass cloud deployment delays and rapidly prototype during the hackathon.
- **SMS Notifications:** Integrates with AWS SNS to instantly alert registered recyclers whenever a new e-waste lot is uploaded and ready for bidding.

## 🛠️ Tech Stack

- **Frontend:** React (Vite), CSS3
- **Backend/Cloud (AWS SAM):**
  - **AWS Lambda** (Python) for processing image uploads and triggering alerts
  - **Amazon Bedrock** (Claude 3 Haiku vision) for intelligent image analysis
  - **Amazon DynamoDB** for storing e-waste lots and bidding details
  - **Amazon S3** for secure image storage
  - **Amazon SNS** for sending SMS notifications to recyclers
- **Local API:** Python (`http.server`) & Boto3 (for direct Bedrock interaction in local mode)

## 📂 Project Structure

- `frontend/` - The React frontend application.
- `analyze_image/` - AWS Lambda function that handles S3/API Gateway uploads, invokes Bedrock for image analysis, and saves the e-waste lot to DynamoDB.
- `send_alert/` - AWS Lambda function triggered by DynamoDB Streams that sends an SMS to recyclers via SNS when a new lot is recorded.
- `local_api.py` - Local development API server mocking the `AnalyzeImageFunction`. This speeds up frontend development without deploying full resources to AWS.
- `template.yaml` - AWS Serverless Application Model (SAM) template for deploying the cloud resources.

## 🏃‍♂️ Getting Started (Local Development)

To run the project locally without deploying the full AWS stack:

### 1. Start the Local API
The local API connects to AWS Bedrock directly and stores data in memory, bypassing the need for a live DynamoDB/S3 setup.
*Prerequisite: You need AWS CLI credentials configured (`aws configure`) with access to invoke Amazon Bedrock.*

```bash
# From the root directory
python local_api.py
```
*The local server will run on `http://127.0.0.1:3000`.*

### 2. Start the Frontend
In a new terminal window, start the Vite development server:

```bash
cd frontend
npm install
npm run dev
```
*The React application will be available at `http://localhost:5173`.*

## ☁️ Deployment (AWS SAM)

To deploy the full serverless stack to your AWS account:

```bash
sam build
sam deploy --guided
```
After deployment, copy the `AnalyzeApiUrl` output provided by SAM and set it as the `VITE_API_URL` environment variable in your frontend project's `.env` file.

## 📝 License
Built for hackathon innovation. Open source and free to use!
