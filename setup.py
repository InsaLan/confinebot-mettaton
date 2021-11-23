import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='mettaton',  
    version='0.0.0',
    scripts=[''] ,
    author="Lymkwi",
    author_email="lymkwi@vulpinecitrus.info",
    description="The Friendly(?) Game Server Cluster Manager",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Insalan/mettaton",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Linux",
    ],
 )