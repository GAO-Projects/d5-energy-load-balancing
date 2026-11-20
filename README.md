## D5: Energy Load Balancing
Welcome to the Physical AI Implementation of the D5: Energy Load Balancing project. 

The following diagram is the project's directory structure: 

```text
d5-energy-load-balancing/
├── docker-compose.yml               
├── mosquitto/
│   └── config/
│       └── mosquitto.conf          
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                  
│       ├── config.py                
│       ├── database.py              
│       ├── models.py               
│       ├── hal/
│       │   ├── base.py              
│       │   ├── gao_gateway.py       
│       │   ├── serial_controller.py 
│       │   └── synthetic.py
│       └── ai/
│           ├── forecaster.py        
│           └── optimizer.py         
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── tsconfig.json
    ├── tailwind.config.ts
    └── src/
        └── app/
            ├── layout.tsx
            ├── globals.css
            └── page.tsx             
```
Using python for the backend along with JavaScript, TypeScript, and CSS for the front end, this program accurately simulates the D5 project's priority encoding system. 

If you have any questions regarding the project or development of this project, please feel free to reach out to me via Teams or E-Mail.

University E-Mail: aanwar08@uoguelph.ca
Personal E-Mail: alvinaianwar@gmail.com

#This project was implemented by Alvina Anwar.
