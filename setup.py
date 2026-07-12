from setuptools import setup, find_packages

setup(
    name="ocen_connector",
    version="0.1.0",
    description="Connects vendor ERPNext instances to the OCEN LA platform for receivables financing",
    author="Shreyash Nadage",
    author_email="shreyashnadage@gmail.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[
        "frappe",
        "requests",
    ],
)
